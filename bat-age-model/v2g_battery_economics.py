#!/usr/bin/env python3
"""
v2g_battery_economics.py

Nutzt bat_model_v01_fast.py, um für ein einfaches V2G-Profil zu berechnen:

- zusätzlichen Kapazitätsverlust gegenüber Baseline ohne V2G
- geschätzte Batteriekosten in EUR
- verkaufte Energie
- Erlös
- Netto-Ergebnis

Wichtig:
Diese Datei muss im selben Ordner liegen wie bat_model_v01_fast.py.
"""

from dataclasses import dataclass, asdict
import pandas as pd

import bat_model_v01_fast as bat


SECONDS_PER_HOUR = 3600.0


@dataclass
class V2GCase:
    battery_capacity_kwh: float = 60.0
    initial_soc: float = 0.70
    min_soc: float = 0.30

    discharge_power_kw: float = 10.0
    discharge_duration_h: float = 2.0

    recharge_power_kw: float = 10.0
    ambient_temperature_c: float = 20.0

    dt_seconds: int = 900  # 15 Minuten, passend zu vielen Strommarktdaten
    battery_replacement_cost_eur: float = 9000.0
    sell_price_eur_per_kwh: float = 0.30
    buy_price_eur_per_kwh: float = 0.15

    # Wenn True, wird nach V2G ungefähr die gleiche Energiemenge wieder geladen.
    recharge_after_discharge: bool = True


def vehicle_power_to_cell_power_kw(
    vehicle_power_kw: float,
    battery_capacity_kwh: float,
) -> float:
    """
    Das Batteriemodell simuliert eine einzelne Zelle.
    Daher muss Fahrzeugleistung auf Zellleistung heruntergerechnet werden.
    """
    n_cells_equivalent = (battery_capacity_kwh * 1000.0) / bat.E_NOMINAL
    cell_power_w = (vehicle_power_kw * 1000.0) / n_cells_equivalent
    return cell_power_w / 1000.0


def build_v2g_profile(case: V2GCase) -> pd.Series:
    """
    Erst V2G-Entladung, optional danach Nachladen.
    Rückgabe: pandas.Series mit Zellleistung in W.
    Vorzeichen:
      + = Laden
      - = Entladen
    """
    n_discharge_steps = int(round(case.discharge_duration_h * SECONDS_PER_HOUR / case.dt_seconds))

    p_discharge_cell_kw = vehicle_power_to_cell_power_kw(
        -abs(case.discharge_power_kw),
        case.battery_capacity_kwh,
    )
    p_discharge_cell_w = p_discharge_cell_kw * 1000.0

    values = [p_discharge_cell_w] * n_discharge_steps

    if case.recharge_after_discharge:
        discharged_energy_kwh = abs(case.discharge_power_kw) * case.discharge_duration_h
        recharge_duration_h = discharged_energy_kwh / abs(case.recharge_power_kw)
        n_recharge_steps = int(round(recharge_duration_h * SECONDS_PER_HOUR / case.dt_seconds))

        p_recharge_cell_kw = vehicle_power_to_cell_power_kw(
            abs(case.recharge_power_kw),
            case.battery_capacity_kwh,
        )
        p_recharge_cell_w = p_recharge_cell_kw * 1000.0

        values += [p_recharge_cell_w] * n_recharge_steps

    index = [i * case.dt_seconds for i in range(len(values))]
    return pd.Series(values, index=index, dtype=float)


def build_baseline_profile(case: V2GCase, same_length_as: pd.Series) -> pd.Series:
    """
    Baseline: Fahrzeug steht gleich lange, aber ohne V2G.
    Dadurch wird Kalenderalterung fair mitgerechnet.
    """
    return pd.Series(0.0, index=same_length_as.index, dtype=float)


def run_profile(case: V2GCase, p_cell_w: pd.Series) -> dict:
    """
    Führt ein Leistungsprofil durch und gibt Modelloutputs + Energiebilanz zurück.
    """
    cap_aged, aging_states, temp_cell, soc = bat.init(
        storage_soc=case.initial_soc,
        storage_temperature=case.ambient_temperature_c,
    )

    cap_start = cap_aged

    cap_end, aging_states_end, temp_cell_end, soc_end, t_next, p_actual_cell_w = (
        bat.apply_power_profile_soc_lim(
            t_start=0,
            dt_resolution=case.dt_seconds,
            p_set_df=p_cell_w,
            temp_amb=case.ambient_temperature_c,
            cap_aged=cap_aged,
            aging_states=aging_states,
            temp_cell=temp_cell,
            soc=soc,
            soc_min=case.min_soc,
        )
    )

    n_cells_equivalent = (case.battery_capacity_kwh * 1000.0) / bat.E_NOMINAL

    # Energie aus tatsächlich realisierter Zellleistung berechnen.
    # p_actual_cell_w ist pro Zelle.
    energy_cell_wh = p_actual_cell_w * case.dt_seconds / SECONDS_PER_HOUR
    energy_vehicle_kwh_series = energy_cell_wh * n_cells_equivalent / 1000.0

    charged_kwh = energy_vehicle_kwh_series[energy_vehicle_kwh_series > 0].sum()
    discharged_kwh = -energy_vehicle_kwh_series[energy_vehicle_kwh_series < 0].sum()

    return {
        "cap_start_ah": cap_start,
        "cap_end_ah": cap_end,
        "capacity_loss_ah": cap_start - cap_end,
        "capacity_loss_fraction_of_nominal": (cap_start - cap_end) / bat.CAP_NOMINAL,
        "soc_end": soc_end,
        "temp_cell_end_c": temp_cell_end,
        "t_next_s": t_next,
        "charged_kwh": charged_kwh,
        "discharged_kwh": discharged_kwh,
        "aging_states": aging_states_end,
        "p_actual_cell_w": p_actual_cell_w,
    }


def evaluate_v2g_case(case: V2GCase) -> dict:
    """
    Vergleicht:
      Baseline: gleiche Zeit, keine V2G-Leistung
      V2G: Entladen + optional Nachladen

    Der relevante Batterieschaden ist die Differenz.
    """
    v2g_profile = build_v2g_profile(case)
    baseline_profile = build_baseline_profile(case, v2g_profile)

    baseline = run_profile(case, baseline_profile)
    v2g = run_profile(case, v2g_profile)

    additional_capacity_loss_ah = baseline["cap_end_ah"] - v2g["cap_end_ah"]
    additional_capacity_loss_fraction = additional_capacity_loss_ah / bat.CAP_NOMINAL
    additional_capacity_loss_percent = additional_capacity_loss_fraction * 100.0

    battery_damage_eur = additional_capacity_loss_fraction * case.battery_replacement_cost_eur

    revenue_eur = v2g["discharged_kwh"] * case.sell_price_eur_per_kwh
    recharge_cost_eur = v2g["charged_kwh"] * case.buy_price_eur_per_kwh
    net_profit_eur = revenue_eur - recharge_cost_eur - battery_damage_eur

    if v2g["discharged_kwh"] > 0:
        degradation_cost_eur_per_kwh_sold = battery_damage_eur / v2g["discharged_kwh"]
    else:
        degradation_cost_eur_per_kwh_sold = float("nan")

    return {
        "input": asdict(case),

        "baseline_capacity_loss_percent": baseline["capacity_loss_fraction_of_nominal"] * 100.0,
        "v2g_capacity_loss_percent": v2g["capacity_loss_fraction_of_nominal"] * 100.0,

        "additional_capacity_loss_ah": additional_capacity_loss_ah,
        "additional_capacity_loss_percent": additional_capacity_loss_percent,

        "battery_damage_eur": battery_damage_eur,
        "degradation_cost_eur_per_kwh_sold": degradation_cost_eur_per_kwh_sold,

        "energy_sold_kwh": v2g["discharged_kwh"],
        "energy_recharged_kwh": v2g["charged_kwh"],

        "revenue_eur": revenue_eur,
        "recharge_cost_eur": recharge_cost_eur,
        "net_profit_eur": net_profit_eur,

        "baseline_soc_end": baseline["soc_end"],
        "v2g_soc_end": v2g["soc_end"],
    }


def print_result(result: dict) -> None:
    print("\n=== V2G Battery Economics Result ===")
    print(f"Battery capacity:              {result['input']['battery_capacity_kwh']:.1f} kWh")
    print(f"Initial SoC:                   {result['input']['initial_soc'] * 100:.1f} %")
    print(f"Minimum SoC:                   {result['input']['min_soc'] * 100:.1f} %")
    print(f"Discharge power:               {result['input']['discharge_power_kw']:.1f} kW")
    print(f"Discharge duration:            {result['input']['discharge_duration_h']:.2f} h")

    print("\n--- Battery degradation ---")
    print(f"Baseline capacity loss:        {result['baseline_capacity_loss_percent']:.6f} %")
    print(f"V2G capacity loss:             {result['v2g_capacity_loss_percent']:.6f} %")
    print(f"Additional V2G capacity loss:  {result['additional_capacity_loss_percent']:.6f} %")
    print(f"Battery damage:                {result['battery_damage_eur']:.4f} EUR")
    print(f"Damage per kWh sold:           {result['degradation_cost_eur_per_kwh_sold']:.4f} EUR/kWh")

    print("\n--- Energy and money ---")
    print(f"Energy sold:                   {result['energy_sold_kwh']:.3f} kWh")
    print(f"Energy recharged:              {result['energy_recharged_kwh']:.3f} kWh")
    print(f"Revenue:                       {result['revenue_eur']:.4f} EUR")
    print(f"Recharge cost:                 {result['recharge_cost_eur']:.4f} EUR")
    print(f"Net profit:                    {result['net_profit_eur']:.4f} EUR")

    print("\n--- End state ---")
    print(f"Baseline end SoC:              {result['baseline_soc_end'] * 100:.2f} %")
    print(f"V2G end SoC:                   {result['v2g_soc_end'] * 100:.2f} %")


if __name__ == "__main__":
    # Beispielaufruf:
    # 60-kWh-Auto, startet bei 70 % SoC,
    # verkauft 2 Stunden lang 10 kW ans Netz,
    # lädt danach mit 10 kW wieder nach.
    case = V2GCase(
        battery_capacity_kwh=60.0,
        initial_soc=0.70,
        min_soc=0.30,
        discharge_power_kw=10.0,
        discharge_duration_h=2.0,
        recharge_power_kw=10.0,
        ambient_temperature_c=20.0,
        dt_seconds=900,
        battery_replacement_cost_eur=9000.0,
        sell_price_eur_per_kwh=0.30,
        buy_price_eur_per_kwh=0.15,
        recharge_after_discharge=True,
    )

    result = evaluate_v2g_case(case)
    print_result(result)

    # Beispiel für mehrere Inputs:
    print("\n\n=== Sensitivity: verschiedene Entladeleistungen ===")
    for power_kw in [3.7, 7.4, 11.0, 22.0]:
        case.discharge_power_kw = power_kw
        case.recharge_power_kw = power_kw
        result = evaluate_v2g_case(case)
        print(
            f"{power_kw:>5.1f} kW | "
            f"sold={result['energy_sold_kwh']:>6.2f} kWh | "
            f"damage={result['battery_damage_eur']:>8.4f} EUR | "
            f"net={result['net_profit_eur']:>8.4f} EUR"
        )
