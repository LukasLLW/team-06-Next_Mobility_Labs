"""
test_step8.py
=============

Testskript fuer SCHRITT 8 (k-Kalibrierung, Baseline-Fallback, FCR-Verschleiss).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step8

Es deckt die drei Punkte aus der Diskussion ab:
  1) Fixpunkt-Kalibrierung von k (selbstkonsistenter Strafterm).
  2) Baseline-Fallback: der ehrlich realisierbare Netto-Gewinn faellt nie < 0.
  3) FCR-Verschleiss best vs worst case (Bandbreite des Netto-Gewinns).

Auto 1, mit FCR. Laufzeit ca. 4-6 Minuten (mehrere Optimierer- + KIT-Laeufe).
"""

from __future__ import annotations

import time
from pathlib import Path

from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import evaluate_scenario
from engine.step7_load_fcr_prices import load_fcr_timeline
from engine.step8_calibrate_wear import calibrate_wear_cost

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def main():
    print("=" * 76)
    print("SCHRITT 8 TEST: k-Kalibrierung + Fallback + FCR-Verschleiss (Auto 1)")
    print("=" * 76)

    trips, tl = load_car_timeline(CAR_CSV)
    price_kwh = load_price_timeline() / 1000.0
    fcr_kw_step = load_fcr_timeline() / 1000.0    # EUR/MW -> EUR/kW pro Schritt
    bat = BatteryModel()

    print("\nBaseline berechnen (nur laden, kein V2G)...")
    t0 = time.time()
    baseline = run_rolling_year(price_kwh, tl.consumption_kwh, tl.plugged_in,
                                bat, allow_discharge=False)
    print(f"  fertig ({time.time()-t0:.0f}s)")

    # --- 1) k kalibrieren (mit FCR aktiv) ---------------------------------
    print("\n1) Fixpunkt-Kalibrierung von k (mit FCR):")
    t0 = time.time()
    calib = calibrate_wear_cost(
        price_kwh, tl.consumption_kwh, tl.plugged_in, bat,
        baseline_plan=baseline,
        fcr_price_eur_per_kw_per_step=fcr_kw_step,
    )
    print(f"  fertig ({time.time()-t0:.0f}s)")
    check("Kalibrierung konvergiert", calib.converged,
          f"k_final = {calib.k_final*100:.2f} ct/kWh")

    # --- 2+3) Szenario mit kalibriertem k bewerten ------------------------
    print(f"\n2+3) Szenario mit kalibriertem k = {calib.k_final*100:.2f} ct/kWh, "
          "best/worst FCR-Verschleiss:")
    t0 = time.time()
    s = evaluate_scenario(
        price_kwh, tl.consumption_kwh, tl.plugged_in, bat,
        wear_cost_per_kwh=calib.k_final,
        baseline_charge_kwh=baseline.charge_kwh,
        baseline_discharge_kwh=baseline.discharge_kwh,
        fcr_price_eur_per_kw_per_step=fcr_kw_step,
    )
    print(f"  fertig ({time.time()-t0:.0f}s)")

    # --- Ergebnis ---------------------------------------------------------
    print("\n" + "=" * 76)
    print("ERGEBNIS (Auto 1, 2025, Arbitrage + FCR, kalibriertes k)")
    print("=" * 76)
    print(f"  Arbitrage-Gewinn         : {s.trading_profit_eur:8.0f} EUR")
    print(f"  FCR-Erloes               : {s.fcr_revenue_eur:8.0f} EUR")
    print(f"  Einnahmen gesamt         : {s.trading_profit_eur + s.fcr_revenue_eur:8.0f} EUR")
    print("  " + "-" * 50)
    print(f"  Degradation BEST  (kein FCR-Abruf) : {s.degradation_cost_eur:8.0f} EUR "
          f"(Mehralt. {s.extra_fade_percent:.2f} %/Jahr)")
    print(f"  Degradation WORST (FCR voll Abruf) : {s.degradation_cost_worst_eur:8.0f} EUR "
          f"(Mehralt. {s.extra_fade_percent_worst:.2f} %/Jahr)")
    print("  " + "-" * 50)
    print(f"  NETTO best case          : {s.net_profit_eur:8.0f} EUR")
    print(f"  NETTO worst case         : {s.net_profit_worst_eur:8.0f} EUR")
    print(f"  NETTO realisierbar (Fallback max(0,.)) : {s.net_realized_eur:8.0f} EUR")
    print(f"  Baseline-Fallback aktiv? : {s.fallback_used}")
    print("=" * 76)

    # --- Checks -----------------------------------------------------------
    print("\nAutomatische Pruefungen:")
    check("realisierter Netto-Gewinn ist nie negativ", s.net_realized_eur >= 0,
          f"{s.net_realized_eur:.0f} EUR")
    check("worst case altert mehr als best case (FCR-Verschleiss > 0)",
          s.degradation_cost_worst_eur >= s.degradation_cost_eur - 1e-6,
          f"worst {s.degradation_cost_worst_eur:.0f} >= best {s.degradation_cost_eur:.0f} EUR")
    check("best-case Netto >= worst-case Netto",
          s.net_profit_eur >= s.net_profit_worst_eur - 1e-6,
          f"{s.net_profit_eur:.0f} >= {s.net_profit_worst_eur:.0f}")

    print("\n  Interpretation:")
    print(f"  - Selbst im worst case (FCR dauernd voll abgerufen) liegt der Netto-")
    print(f"    Gewinn bei {s.net_profit_worst_eur:.0f} EUR, im best case bei {s.net_profit_eur:.0f} EUR.")
    print("  - Der Baseline-Fallback stellt sicher, dass nie ein Verlust 'erzwungen'")
    print("    wird: faellt der Plan ins Minus, macht der Kunde einfach kein V2G.")


if __name__ == "__main__":
    main()
