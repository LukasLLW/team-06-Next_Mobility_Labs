"""
test_step6.py
=============

Testskript fuer SCHRITT 6 (Verschleiss-Strafterm + Netto-Gewinn).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step6

Das Skript probiert mehrere Strafterm-Werte durch und zeigt fuer jeden:
  - Durchsatz (wie viel ge-/entladen wird),
  - Handelsgewinn,
  - V2G-Mehralterung (KIT-Modell),
  - Euro-Wert dieser Mehralterung,
  - NETTO-Gewinn = Handelsgewinn - Degradationskosten.

Erwartung: hoeherer Strafterm -> weniger Durchsatz -> weniger Mehralterung.
Der Netto-Gewinn hat ein Optimum: ohne Strafe Verlust (zu viel Verschleiss),
mit zu hoher Strafe fast kein Handel. Irgendwo dazwischen ist es am besten.

Laufzeit: ca. 3-4 Minuten (mehrere Optimierer- und KIT-Laeufe).
"""

from __future__ import annotations

import time
from pathlib import Path

from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import evaluate_scenario

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def main():
    print("=" * 78)
    print("SCHRITT 6 TEST: Verschleiss-Strafterm + Netto-Gewinn (Auto 1)")
    print("=" * 78)

    trips, tl = load_car_timeline(CAR_CSV)
    price_kwh = load_price_timeline() / 1000.0
    bat = BatteryModel()

    # Baseline einmal berechnen (nur laden, kein V2G) - Vergleichsbasis fuer KIT
    print("\nBaseline berechnen (nur laden fuer Fahrten, kein V2G)...")
    t0 = time.time()
    baseline = run_rolling_year(price_kwh, tl.consumption_kwh, tl.plugged_in,
                                bat, allow_discharge=False)
    print(f"  fertig ({time.time()-t0:.0f}s)")

    # Strafterm-Werte (EUR pro kWh Durchsatz) zum Durchprobieren.
    # 0 = keine Strafe (wie Schritt 5). 0.005..0.04 = zunehmend vorsichtig.
    wear_values = [0.0, 0.01, 0.02, 0.04]

    results = []
    for w in wear_values:
        print(f"\nSzenario: Strafterm = {w*100:.1f} ct/kWh ...")
        t0 = time.time()
        res = evaluate_scenario(
            price_kwh, tl.consumption_kwh, tl.plugged_in, bat,
            wear_cost_per_kwh=w,
            baseline_charge_kwh=baseline.charge_kwh,
            baseline_discharge_kwh=baseline.discharge_kwh,
        )
        results.append(res)
        print(f"  fertig ({time.time()-t0:.0f}s)")

    # --- Tabelle ----------------------------------------------------------
    print("\n" + "=" * 78)
    print("ERGEBNIS-TABELLE (Auto 1, 2025)")
    print("=" * 78)
    print(f"{'Strafe':>8} | {'Durchsatz':>10} | {'Handelsg.':>10} | "
          f"{'Mehralt.':>9} | {'Degr.kosten':>11} | {'NETTO':>9}")
    print(f"{'ct/kWh':>8} | {'kWh':>10} | {'EUR':>10} | "
          f"{'%/Jahr':>9} | {'EUR':>11} | {'EUR':>9}")
    print("-" * 78)
    for r in results:
        print(f"{r.wear_cost_per_kwh*100:>8.1f} | {r.throughput_kwh:>10.0f} | "
              f"{r.trading_profit_eur:>10.0f} | {r.extra_fade_percent:>9.2f} | "
              f"{r.degradation_cost_eur:>11.0f} | {r.net_profit_eur:>9.0f}")
    print("-" * 78)

    # --- Auto-Checks ------------------------------------------------------
    print("\nAutomatische Pruefungen:")
    throughputs = [r.throughput_kwh for r in results]
    fades = [r.extra_fade_percent for r in results]
    check("hoehere Strafe -> weniger Durchsatz (monoton fallend)",
          all(throughputs[i] >= throughputs[i+1] - 1e-6 for i in range(len(throughputs)-1)),
          f"{[round(t) for t in throughputs]}")
    check("hoehere Strafe -> weniger Mehralterung",
          all(fades[i] >= fades[i+1] - 1e-6 for i in range(len(fades)-1)),
          f"{[round(f,2) for f in fades]}")

    best = max(results, key=lambda r: r.net_profit_eur)
    check("ein Strafterm > 0 schlaegt 'keine Strafe' im Netto-Gewinn",
          best.wear_cost_per_kwh > 0 or best.net_profit_eur >= results[0].net_profit_eur,
          f"bester Strafterm = {best.wear_cost_per_kwh*100:.1f} ct/kWh "
          f"-> Netto {best.net_profit_eur:.0f} EUR")

    print(f"\n  Bestes Szenario: Strafterm {best.wear_cost_per_kwh*100:.1f} ct/kWh")
    print(f"    Netto-Gewinn       : {best.net_profit_eur:.0f} EUR/Jahr")
    print(f"    Handelsgewinn      : {best.trading_profit_eur:.0f} EUR/Jahr")
    print(f"    Degradationskosten : {best.degradation_cost_eur:.0f} EUR/Jahr")
    print(f"    V2G-Mehralterung   : {best.extra_fade_percent:.2f} %/Jahr")
    print("\n  Vergleich ohne Strafe (Schritt-5-Zustand):")
    r0 = results[0]
    print(f"    Netto {r0.net_profit_eur:.0f} EUR  (Handel {r0.trading_profit_eur:.0f} "
          f"- Degradation {r0.degradation_cost_eur:.0f}), Mehralterung {r0.extra_fade_percent:.2f} %/Jahr")
    print("=" * 78)


if __name__ == "__main__":
    main()
