"""
run_demo.py
===========

Das Haupt-Demoskript: rechnet die komplette Pipeline (Schritte 1-9) fuer EIN
Auto durch und gibt eine verstaendliche Ergebnis-Uebersicht aus.

    python -m engine.run_demo                       # Auto 1, Standardannahmen
    python -m engine.run_demo --car 3 --pool 120    # Auto 3, Pool mit 120 Autos

Ablauf:
  1) Fahrtdaten einlesen        (Schritt 1)
  2) Day-Ahead-Preise laden     (Schritt 2)
  3) FCR-Preise laden           (Schritt 7a)
  4) Baseline optimieren        (Schritt 4, ohne V2G)
  5) Verschleiss-Strafterm k kalibrieren (Schritt 8)
  6) V2G+FCR mit kalibriertem k optimieren und mit KIT bewerten (Schritte 4-9)
  7) Netto-Gewinn (best/worst, Fallback) + Cold-Start-Kennzahl ausgeben
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from engine import config
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline, price_source
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import evaluate_scenario
from engine.step7_load_fcr_prices import load_fcr_timeline, fcr_source
from engine.step8_calibrate_wear import calibrate_wear_cost
from engine.step9_fcr_pool import min_pool_size_for_fcr

DEMO_DIR = Path(__file__).resolve().parent.parent / "demodata"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--car", type=int, default=1, help="Auto-Nummer (1..20)")
    ap.add_argument("--pool", type=int, default=None,
                    help="Anzahl Autos im FCR-Pool (Default: als ausreichend angenommen)")
    ap.add_argument("--no-fcr", action="store_true", help="ohne FCR rechnen")
    args = ap.parse_args()

    car_csv = DEMO_DIR / f"fahrtdaten_2025_{args.car:02d}.csv"
    bat = BatteryModel()

    print("=" * 74)
    print(f"PLUG & EARN - V2G-Ertragssimulation (Auto {args.car:02d}, Jahr {config.YEAR})")
    print("=" * 74)
    print(f"Akku: {bat.capacity_kwh:.0f} kWh, {bat.power_kw:.0f} kW, "
          f"SoC {bat.soc_min_frac*100:.0f}-{bat.soc_max_frac*100:.0f} %, "
          f"Kosten {config.BATTERY_COST_EUR_PER_KWH:.0f} EUR/kWh, "
          f"EoL bei {config.BATTERY_EOL_LOSS_PCT:.0f} % Verlust")

    # --- Daten laden ---
    trips, tl = load_car_timeline(car_csv)
    price = load_price_timeline() / 1000.0
    fcr = (None if args.no_fcr else load_fcr_timeline() / 1000.0)
    print(f"Fahrten: {len(trips)} | Verbrauch: {tl.consumption_kwh.sum():.0f} kWh/Jahr | "
          f"angesteckt: {tl.plugged_in.mean()*24:.1f} h/Tag")
    print(f"Preise: Day-Ahead={price_source()}"
          + (f", FCR={fcr_source()}" if not args.no_fcr else ""))

    # --- Baseline ---
    print("\n[1/3] Baseline optimieren (nur laden, kein V2G)...")
    t0 = time.time()
    baseline = run_rolling_year(price, tl.consumption_kwh, tl.plugged_in, bat,
                                allow_discharge=False)
    print(f"      fertig ({time.time()-t0:.0f}s)")

    # --- k kalibrieren ---
    print("[2/3] Verschleiss-Strafterm k kalibrieren...")
    t0 = time.time()
    calib = calibrate_wear_cost(price, tl.consumption_kwh, tl.plugged_in, bat,
                                baseline_plan=baseline,
                                fcr_price_eur_per_kw_per_step=fcr, verbose=False)
    print(f"      fertig ({time.time()-t0:.0f}s), k = {calib.k_final*100:.2f} ct/kWh")

    # --- Szenario bewerten ---
    print("[3/3] V2G+FCR optimieren und mit KIT-Modell bewerten...")
    t0 = time.time()
    s = evaluate_scenario(price, tl.consumption_kwh, tl.plugged_in, bat,
                          wear_cost_per_kwh=calib.k_final,
                          baseline_charge_kwh=baseline.charge_kwh,
                          baseline_discharge_kwh=baseline.discharge_kwh,
                          fcr_price_eur_per_kw_per_step=fcr,
                          pool_size=args.pool)
    print(f"      fertig ({time.time()-t0:.0f}s)")

    # --- Ergebnis ---
    print("\n" + "=" * 74)
    print("ERGEBNIS (pro Auto, pro Jahr)")
    print("=" * 74)
    print(f"  Arbitrage-Vorteil (ggue. nur laden) : {s.trading_profit_eur:8.0f} EUR")
    if not args.no_fcr:
        print(f"  FCR-Erloes                          : {s.fcr_revenue_eur:8.0f} EUR")
    print(f"  Einnahmen gesamt                    : "
          f"{s.trading_profit_eur + s.fcr_revenue_eur:8.0f} EUR")
    print("  " + "-" * 56)
    print(f"  Batterie-Mehralterung durch V2G     : {s.extra_fade_percent:7.2f} %/Jahr")
    print(f"  Degradationskosten (EoL-Modell)     : {s.degradation_cost_eur:8.0f} EUR")
    print("  " + "-" * 56)
    print(f"  NETTO-GEWINN (best case)            : {s.net_profit_eur:8.0f} EUR")
    if not args.no_fcr:
        print(f"  NETTO-GEWINN (worst-case FCR-Abruf) : {s.net_profit_worst_eur:8.0f} EUR")
    print(f"  REALISIERBAR (mit Baseline-Fallback): {s.net_realized_eur:8.0f} EUR")

    if not args.no_fcr and s.plan.fcr_kw is not None:
        n_min = min_pool_size_for_fcr(s.plan.fcr_kw)
        print("  " + "-" * 56)
        print(f"  FCR Cold-Start: Pool braucht >= {n_min} Autos fuer die 1-MW-Schwelle")
    print("=" * 74)


if __name__ == "__main__":
    main()
