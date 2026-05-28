"""
test_step7.py
=============

Testskript fuer SCHRITT 7 (FCR / Regelleistung).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step7

Teil A: prueft den FCR-Preis-Loader (Quelle, Laenge, Ausrichtung).
Teil B: vergleicht auf Auto 1 zwei Szenarien (jeweils mit Verschleiss-Strafe):
          - "nur Arbitrage"      (Day-Ahead-Handel)
          - "Arbitrage + FCR"    (zusaetzlich FCR-Kapazitaet anbieten)
        und zeigt, ob der FCR-Erloes das Geschaeft ins Plus dreht.

Laufzeit: ca. 2-3 Minuten.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from engine.config import STEPS_PER_DAY, TOTAL_STEPS
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel, simulate_soc
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import evaluate_scenario
from engine.step7_load_fcr_prices import load_fcr_timeline, fcr_source

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"

WEAR = 0.02   # Verschleiss-Strafe 2 ct/kWh (Optimum aus Schritt 6)


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def test_A_fcr_loader():
    print("\nTest A: FCR-Preis-Loader")
    fcr_mw = load_fcr_timeline()        # EUR/MW pro 15-Min-Schritt
    check("Quelle ist regelleistung.net", fcr_source() == "regelleistung.net",
          f"Quelle: {fcr_source()}")
    check("Laenge == TOTAL_STEPS", len(fcr_mw) == TOTAL_STEPS, f"{len(fcr_mw)}")
    check("keine NaN", not np.isnan(fcr_mw).any())
    check("Preise positiv", (fcr_mw >= 0).all())
    # innerhalb eines 4h-Blocks (16 Schritte) muss der Preis konstant sein
    block0 = fcr_mw[:16]
    check("Preis konstant innerhalb eines 4h-Blocks", np.allclose(block0, block0[0]),
          f"erste 16 Schritte alle = {block0[0]:.4f}")
    # Mittel pro MW und Tag (Summe ueber 96 Schritte * ... ) zur Orientierung
    mean_per_step = fcr_mw.mean()
    # Erloes pro MW pro Jahr, wenn man durchgehend anbietet:
    yearly_per_mw = fcr_mw.sum()
    print(f"       Mittel {mean_per_step:.4f} EUR/MW/15min  ->  "
          f"durchgehend ~{yearly_per_mw:.0f} EUR/MW/Jahr")
    return fcr_mw


def test_B_arbitrage_vs_fcr(fcr_mw):
    print("\nTest B: nur Arbitrage  vs  Arbitrage + FCR (Auto 1)")
    trips, tl = load_car_timeline(CAR_CSV)
    price_kwh = load_price_timeline() / 1000.0
    fcr_kw_step = fcr_mw / 1000.0       # EUR/MW -> EUR/kW pro Schritt
    bat = BatteryModel()

    print("    Baseline berechnen (nur laden, kein V2G)...")
    t0 = time.time()
    baseline = run_rolling_year(price_kwh, tl.consumption_kwh, tl.plugged_in,
                                bat, allow_discharge=False)
    print(f"      fertig ({time.time()-t0:.0f}s)")

    print("    Szenario 1: nur Arbitrage ...")
    t0 = time.time()
    s_arb = evaluate_scenario(
        price_kwh, tl.consumption_kwh, tl.plugged_in, bat,
        wear_cost_per_kwh=WEAR,
        baseline_charge_kwh=baseline.charge_kwh,
        baseline_discharge_kwh=baseline.discharge_kwh,
    )
    print(f"      fertig ({time.time()-t0:.0f}s)")

    print("    Szenario 2: Arbitrage + FCR ...")
    t0 = time.time()
    s_fcr = evaluate_scenario(
        price_kwh, tl.consumption_kwh, tl.plugged_in, bat,
        wear_cost_per_kwh=WEAR,
        baseline_charge_kwh=baseline.charge_kwh,
        baseline_discharge_kwh=baseline.discharge_kwh,
        fcr_price_eur_per_kw_per_step=fcr_kw_step,
    )
    print(f"      fertig ({time.time()-t0:.0f}s)")

    # SoC-Gegenpruefung des FCR-Plans (Fahrt-Garantie trotz FCR-Puffer)
    soc_check = simulate_soc(
        s_fcr.plan.charge_kwh, s_fcr.plan.discharge_kwh,
        tl.consumption_kwh, tl.plugged_in, bat,
        start_soc_kwh=s_fcr.plan.soc_kwh[0])

    # --- Tabelle ---
    print("\n" + "=" * 74)
    print(f"{'Szenario':<22} | {'Arbitrage':>9} | {'FCR':>8} | {'Degrad.':>8} | {'NETTO':>8}")
    print(f"{'':<22} | {'EUR':>9} | {'EUR':>8} | {'EUR':>8} | {'EUR':>8}")
    print("-" * 74)
    for name, s in [("nur Arbitrage", s_arb), ("Arbitrage + FCR", s_fcr)]:
        print(f"{name:<22} | {s.trading_profit_eur:>9.0f} | {s.fcr_revenue_eur:>8.0f} | "
              f"{s.degradation_cost_eur:>8.0f} | {s.net_profit_eur:>8.0f}")
    print("=" * 74)

    # --- Checks ---
    print("\nAutomatische Pruefungen:")
    check("FCR-Erloes ist positiv", s_fcr.fcr_revenue_eur > 0,
          f"{s_fcr.fcr_revenue_eur:.0f} EUR")
    check("FCR-Plan haelt Fahrt-Garantie (keine SoC-Verstoesse)", soc_check.ok,
          f"{len(soc_check.violations)} Verstoesse")
    check("Arbitrage+FCR hat hoeheren Netto-Gewinn als nur Arbitrage",
          s_fcr.net_profit_eur > s_arb.net_profit_eur,
          f"{s_fcr.net_profit_eur:.0f} > {s_arb.net_profit_eur:.0f} EUR")

    print(f"\n  Fazit: FCR bringt {s_fcr.fcr_revenue_eur:.0f} EUR/Jahr zusaetzlich.")
    print(f"  Netto-Gewinn: {s_arb.net_profit_eur:.0f} EUR (nur Arbitrage) "
          f"-> {s_fcr.net_profit_eur:.0f} EUR (mit FCR).")
    if s_fcr.net_profit_eur > 0 >= s_arb.net_profit_eur:
        print("  -> FCR dreht das Geschaeft vom Verlust ins Plus!")


def main():
    print("=" * 74)
    print("SCHRITT 7 TEST: FCR / Regelleistung")
    print("=" * 74)
    fcr_mw = test_A_fcr_loader()
    test_B_arbitrage_vs_fcr(fcr_mw)
    print("\n" + "=" * 74)
    print("Fertig.")
    print("=" * 74)


if __name__ == "__main__":
    main()
