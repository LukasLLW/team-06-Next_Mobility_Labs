"""
test_step5.py
=============

Testskript fuer SCHRITT 5 (echte Batterie-Alterung mit dem KIT-Modell).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step5

Das Skript:
  A) prueft die Pack->Zell-Umrechnung an einem Handbeispiel,
  B) prueft, dass "mehr Zyklen => mehr Alterung" (Monotonie),
  C) macht den vollen Vergleich auf Auto 1:
       - Baseline (nur Fahren + Laden) und V2G (voller Plan) optimieren,
       - beide mit dem KIT-Modell bewerten,
       - V2G-Mehralterung ausweisen und mit der NREL-Faustregel (~1.8 %/Jahr)
         vergleichen.

Hinweis: Teil C rechnet 2 Optimierer-Laeufe (~je 30 s) und 2 KIT-Laeufe
(~je 25 s). Insgesamt ca. 2 Minuten.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from engine.config import N_DAYS, BATTERY_START_SOC_FRAC
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step5_degradation_kit import (
    CELL_CAP_NOMINAL_AH,
    CELL_E_NOMINAL_WH,
    compare_baseline_vs_v2g,
    n_cells,
    pack_plan_to_cell_power_w,
    simulate_capacity_fade,
)

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


# ---------------------------------------------------------------------------
def test_A_umrechnung():
    print("\nTest A: Pack -> Zell-Umrechnung (Handbeispiel)")
    # 75 kWh / 11 Wh = 6818.18 Zellen
    nc = n_cells(75.0)
    check("Anzahl Zellen 75kWh/11Wh", abs(nc - 75000 / 11) < 1e-6, f"{nc:.1f} Zellen")

    # 1 Schritt: 11 kW laden -> 11*0.25 = 2.75 kWh; Zell-Leistung = 11000W/6818 = 1.61 W
    charge = np.array([2.75])
    discharge = np.array([0.0])
    consumption = np.array([0.0])
    p_cell = pack_plan_to_cell_power_w(charge, discharge, consumption, 75.0)
    expected = 11000.0 / nc
    check("Zell-Ladeleistung bei 11 kW", abs(p_cell[0] - expected) < 1e-6,
          f"{p_cell[0]:.3f} W (erwartet {expected:.3f})")

    # Entladen muss negatives Vorzeichen geben
    p_cell_dis = pack_plan_to_cell_power_w(np.array([0.0]), np.array([2.75]),
                                           np.array([0.0]), 75.0)
    check("Entladen ergibt negative Zell-Leistung", p_cell_dis[0] < 0,
          f"{p_cell_dis[0]:.3f} W")
    print(f"       (Zelle: {CELL_E_NOMINAL_WH} Wh / {CELL_CAP_NOMINAL_AH} Ah nominal)")


# ---------------------------------------------------------------------------
def test_B_monotonie():
    print("\nTest B: mehr Zyklen -> mehr Alterung (dauert ~1 min)")
    from engine.config import TOTAL_STEPS, STEPS_PER_DAY

    # "wenig V2G": pro Tag ein kleiner Lade-/Entlade-Hub
    # "viel V2G":  pro Tag ein grosser Lade-/Entlade-Hub
    def make_profile(amp_w):
        p = np.zeros(TOTAL_STEPS)
        for day in range(N_DAYS):
            s = day * STEPS_PER_DAY
            # vormittags laden, nachmittags entladen (sanft, SoC-erhaltend)
            p[s + 8:s + 16] = amp_w
            p[s + 40:s + 48] = -amp_w
        return p

    t0 = time.time()
    res_low = simulate_capacity_fade(make_profile(0.3), start_soc_frac=0.5)
    res_high = simulate_capacity_fade(make_profile(0.9), start_soc_frac=0.5)
    print(f"       (Laufzeit {time.time()-t0:.0f}s)")

    check("mehr Leistung -> mehr Alterung",
          res_high.fade_percent > res_low.fade_percent,
          f"wenig={res_low.fade_percent:.4f}% < viel={res_high.fade_percent:.4f}%")


# ---------------------------------------------------------------------------
def test_C_baseline_vs_v2g():
    print("\nTest C: Baseline vs V2G auf Auto 1 (voller Vergleich, ~2 min)")
    trips, tl = load_car_timeline(CAR_CSV)
    price_kwh = load_price_timeline() / 1000.0
    bat = BatteryModel()

    print("    1/2: Baseline optimieren (nur laden, kein Entladen)...")
    t0 = time.time()
    base_plan = run_rolling_year(price_kwh, tl.consumption_kwh, tl.plugged_in,
                                 bat, allow_discharge=False)
    print(f"         fertig ({time.time()-t0:.0f}s), "
          f"Baseline geladen: {base_plan.charge_kwh.sum():.0f} kWh, "
          f"entladen: {base_plan.discharge_kwh.sum():.0f} kWh")

    print("    2/2: V2G optimieren (voller Plan)...")
    t0 = time.time()
    v2g_plan = run_rolling_year(price_kwh, tl.consumption_kwh, tl.plugged_in,
                                bat, allow_discharge=True)
    print(f"         fertig ({time.time()-t0:.0f}s), "
          f"V2G Gewinn: {v2g_plan.total_profit_eur:.0f} EUR, "
          f"entladen: {v2g_plan.discharge_kwh.sum():.0f} kWh")

    print("    KIT-Modell bewertet beide Plaene...")
    t0 = time.time()
    cmp = compare_baseline_vs_v2g(
        base_plan.charge_kwh, base_plan.discharge_kwh,
        v2g_plan.charge_kwh, v2g_plan.discharge_kwh,
        tl.consumption_kwh, bat,
    )
    print(f"         fertig ({time.time()-t0:.0f}s)")

    # Plausibilitaet
    check("Baseline altert weniger als V2G",
          cmp.baseline.fade_percent < cmp.v2g.fade_percent,
          f"Baseline={cmp.baseline.fade_percent:.3f}% < V2G={cmp.v2g.fade_percent:.3f}%")
    check("V2G-Mehralterung ist positiv", cmp.extra_fade_percent > 0,
          f"{cmp.extra_fade_percent:.3f} %/Jahr")

    print("\n  Ergebnis Auto 1, 2025 (volles KIT-Modell):")
    print(f"    Baseline-Alterung (nur Fahren+Laden): {cmp.baseline.fade_percent:.3f} %/Jahr")
    print(f"    V2G-Alterung      (mit Netzhandel)  : {cmp.v2g.fade_percent:.3f} %/Jahr")
    print(f"    -> V2G-MEHRALTERUNG                 : {cmp.extra_fade_percent:.3f} %/Jahr")
    print(f"    NREL-Faustregel (Referenz)          : ~1.8 %/Jahr")
    print(f"    V2G-Gewinn vor Degradation          : {v2g_plan.total_profit_eur:.0f} EUR/Jahr")
    print("\n  (Interpretation: ist die Mehralterung viel groesser als 1.8%, zyklt")
    print("   der Optimierer zu aggressiv -> Motivation fuer Schritt 6: Degradations-")
    print("   kosten in den Optimierer einbauen, damit er sich zurueckhaelt.)")


def main():
    print("=" * 70)
    print("SCHRITT 5 TEST: Batterie-Alterung mit dem KIT-Modell (Variante B)")
    print("=" * 70)
    test_A_umrechnung()
    test_B_monotonie()
    test_C_baseline_vs_v2g()
    print("\n" + "=" * 70)
    print("Fertig.")
    print("=" * 70)


if __name__ == "__main__":
    main()
