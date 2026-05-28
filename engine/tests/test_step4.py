"""
test_step4.py
=============

Testskript fuer SCHRITT 4 (Optimierer).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step4

Tests:
  A) Arbitrage-Logik: bei billig-dann-teuer-Preisen muss der Optimierer
     billig laden und teuer entladen.
  B) Fahrt-Garantie: selbst bei verlockenden Entladepreisen haelt er genug
     Energie fuer eine kommende Fahrt zurueck.
  C) Voller Jahreslauf auf Auto 1: Gewinn, Laufzeit - und der erzeugte Plan
     wird mit dem Akku-Modell aus Schritt 3 GEGENGEPRUEFT (keine Verstoesse).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from engine.config import STEPS_PER_DAY
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel, simulate_soc
from engine.step4_optimizer import optimize_window, run_rolling_year

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


# ---------------------------------------------------------------------------
def test_A_arbitrage():
    print("\nTest A: Arbitrage - billig laden, teuer entladen")
    bat = BatteryModel(capacity_kwh=75, power_kw=11)   # SoC 7.5 .. 67.5 kWh
    N = STEPS_PER_DAY                                  # 1 Tag
    # Erste Haelfte billig (5 ct/kWh), zweite Haelfte teuer (30 ct/kWh)
    price = np.empty(N)
    price[: N // 2] = 0.05
    price[N // 2:] = 0.30
    consumption = np.zeros(N)            # keine Fahrten
    plugged = np.ones(N, dtype=bool)     # immer angesteckt

    res = optimize_window(price, consumption, plugged, bat, start_soc_kwh=30.0)

    charged_cheap = res.charge_kwh[: N // 2].sum()
    discharged_exp = res.discharge_kwh[N // 2:].sum()
    charged_exp = res.charge_kwh[N // 2:].sum()

    check("loesbar (feasible)", res.feasible)
    check("laedt in der billigen Phase", charged_cheap > 1.0,
          f"{charged_cheap:.1f} kWh geladen")
    check("entlaedt in der teuren Phase", discharged_exp > 1.0,
          f"{discharged_exp:.1f} kWh entladen")
    check("laedt NICHT in der teuren Phase", charged_exp < 1e-6,
          f"{charged_exp:.3f} kWh")
    check("Gewinn ist positiv", res.profit_eur > 0,
          f"Gewinn {res.profit_eur:.2f} EUR")
    print(f"       SoC: Start 30.0 -> Max {res.soc_kwh.max():.1f} -> "
          f"Ende {res.soc_kwh[-1]:.1f} kWh")


# ---------------------------------------------------------------------------
def test_B_fahrt_garantie():
    print("\nTest B: Fahrt-Garantie - genug fuer eine grosse Mittagsfahrt halten")
    bat = BatteryModel(capacity_kwh=75, power_kw=11, soc_min_frac=0.10)  # min 7.5
    N = STEPS_PER_DAY
    # Morgens SEHR hoher Preis (verlockt zum Entladen), danach billig.
    price = np.full(N, 0.05)
    price[:48] = 1.00                    # 00:00-12:00 sehr teuer
    consumption = np.zeros(N)
    consumption[48] = 50.0               # 12:00: riesige Fahrt (50 kWh!)
    plugged = np.ones(N, dtype=bool)     # zur Verschaerfung: immer angesteckt
    plugged[48] = False                  # waehrend der Fahrt nicht angesteckt

    start_soc = 60.0
    res = optimize_window(price, consumption, plugged, bat, start_soc_kwh=start_soc)

    soc_before_trip = res.soc_kwh[48]    # SoC genau vor der Fahrt
    soc_after_trip = res.soc_kwh[49]     # SoC nach der Fahrt

    check("loesbar (feasible)", res.feasible)
    check("genug SoC VOR der Fahrt (>= 50 + 7.5 = 57.5 kWh)",
          soc_before_trip >= 57.5 - 1e-6, f"{soc_before_trip:.2f} kWh")
    check("SoC nach der Fahrt >= Minimum (7.5 kWh)",
          soc_after_trip >= 7.5 - 1e-6, f"{soc_after_trip:.2f} kWh")
    check("SoC faellt nie unter das Minimum",
          res.soc_kwh.min() >= 7.5 - 1e-6, f"min {res.soc_kwh.min():.2f} kWh")
    print("       -> Der Optimierer entlaedt morgens nur den UEBERSCHUSS ueber")
    print("          das, was die Mittagsfahrt braucht. Genau das wollen wir.")


# ---------------------------------------------------------------------------
def test_C_jahreslauf():
    print("\nTest C: Voller Jahreslauf auf Auto 1 (rollierend, kein Hellsehen)")
    trips, tl = load_car_timeline(CAR_CSV)
    price_mwh = load_price_timeline()
    price_kwh = price_mwh / 1000.0       # EUR/MWh -> EUR/kWh

    bat = BatteryModel()                 # Standard-Akku aus config.py

    print("    Optimiere 365 Tage rollierend (2 Tage Sicht, 1 Tag umsetzen)...")
    t0 = time.time()
    plan = run_rolling_year(
        price_eur_per_kwh=price_kwh,
        consumption_kwh=tl.consumption_kwh,
        plugged_in=tl.plugged_in,
        battery=bat,
        progress=True,
    )
    dauer = time.time() - t0
    print(f"    Laufzeit: {dauer:.1f} s")

    # --- Gegenpruefung mit dem Akku-Modell aus Schritt 3 -------------------
    # Wir nehmen den erzeugten Plan und lassen ihn unabhaengig nachsimulieren.
    start_soc = plan.soc_kwh[0]
    check_res = simulate_soc(
        plan.charge_kwh, plan.discharge_kwh, tl.consumption_kwh, tl.plugged_in,
        bat, start_soc_kwh=start_soc,
    )

    check("Plan ist physikalisch zulaessig (keine Verstoesse)", check_res.ok,
          f"{len(check_res.violations)} Verstoesse"
          + (f": {check_res.violations[:3]}" if check_res.violations else ""))

    # SoC aus Optimierer und aus Schritt-3-Simulation muessen uebereinstimmen
    soc_diff = np.max(np.abs(check_res.soc_kwh - plan.soc_kwh))
    check("SoC-Verlauf stimmt mit Schritt-3-Simulation ueberein",
          soc_diff < 1e-6, f"max. Abweichung {soc_diff:.2e} kWh")

    check("keine unloesbaren Tage", plan.infeasible_days == 0,
          f"{plan.infeasible_days} Tage")

    # --- Kennzahlen --------------------------------------------------------
    total_charged = plan.charge_kwh.sum()
    total_discharged = plan.discharge_kwh.sum()
    print("\n  Kennzahlen Jahr 2025 (Auto 1, nur Day-Ahead-Arbitrage):")
    print(f"    Gewinn gesamt        : {plan.total_profit_eur:8.2f} EUR")
    print(f"    Gewinn pro Tag       : {plan.total_profit_eur / 365:8.2f} EUR")
    print(f"    geladen   (aus Netz) : {total_charged:8.1f} kWh")
    print(f"    entladen  (ins Netz) : {total_discharged:8.1f} kWh")
    print(f"    gefahren (Verbrauch) : {tl.consumption_kwh.sum():8.1f} kWh")
    print(f"    Durchsatz (Lade+Entlade): {total_charged + total_discharged:8.1f} kWh")
    print("    (Hinweis: Degradationskosten sind hier noch NICHT abgezogen -")
    print("     das kommt in Schritt 5.)")


def main():
    print("=" * 70)
    print("SCHRITT 4 TEST: Optimierer")
    print("=" * 70)
    test_A_arbitrage()
    test_B_fahrt_garantie()
    test_C_jahreslauf()
    print("\n" + "=" * 70)
    print("Fertig.")
    print("=" * 70)


if __name__ == "__main__":
    main()
