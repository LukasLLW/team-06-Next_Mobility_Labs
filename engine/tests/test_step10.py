"""
test_step10.py
==============

Testskript fuer SCHRITT 10 (zeitvariable Verschleiss-Strafe k(SoC)).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step10

Teil A: k(SoC)-Kalibrierung - prueft die U-Form (Raender teuer, Mitte billig).
Teil B: k(SoC)-Plan auf einem kurzen Zeitraum + Vergleich mit konstantem k.

Laufzeit: ca. 1-2 Minuten.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from engine.config import STEPS_PER_DAY
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import degradation_cost_eur
from engine.step5_degradation_kit import compare_baseline_vs_v2g
from engine.step7_load_fcr_prices import load_fcr_timeline
from engine.step8_calibrate_wear import calibrate_wear_cost
from engine.step10_soc_wear import (
    calibrate_k_of_soc, make_k_of_soc, plan_with_soc_wear,
)

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def test_A_k_of_soc():
    print("\nTest A: k(SoC)-Kalibrierung (KIT-Sweep)")
    bat = BatteryModel()
    t0 = time.time()
    soc_grid, k_vals = calibrate_k_of_soc(bat, days=15)
    print(f"    (Laufzeit {time.time()-t0:.0f}s)")
    for m, k in zip(soc_grid, k_vals):
        print(f"      SoC {m*100:3.0f}%  ->  k = {k*100:5.2f} ct/kWh")

    i_min = int(np.argmin(k_vals))
    check("alle k >= 0", (k_vals >= 0).all())
    check("Minimum liegt im mittleren SoC-Bereich (35-65 %)",
          0.35 <= soc_grid[i_min] <= 0.65, f"Minimum bei SoC {soc_grid[i_min]*100:.0f} %")
    check("Raender sind teurer als die Mitte (U-Form)",
          k_vals[0] > k_vals[i_min] and k_vals[-1] > k_vals[i_min],
          f"Rand {k_vals[0]*100:.1f}/{k_vals[-1]*100:.1f} vs Mitte {k_vals[i_min]*100:.1f} ct")
    return soc_grid, k_vals


def test_B_compare(soc_grid, k_vals):
    print("\nTest B: k(SoC) vs konstantes k (14 Tage)")
    trips, tl = load_car_timeline(CAR_CSV)
    s, e = 14 * STEPS_PER_DAY, 28 * STEPS_PER_DAY
    price = (load_price_timeline() / 1000.0)[s:e]
    fcr = (load_fcr_timeline() / 1000.0)[s:e]
    cons = tl.consumption_kwh[s:e]
    plug = tl.plugged_in[s:e]
    bat = BatteryModel()
    base = run_rolling_year(price, cons, plug, bat, allow_discharge=False)
    base_trading = float(np.sum(price * (base.discharge_kwh - base.charge_kwh)))

    def net_of(plan):
        incr = plan.total_profit_eur - base_trading
        cmp = compare_baseline_vs_v2g(base.charge_kwh, base.discharge_kwh,
                                      plan.charge_kwh, plan.discharge_kwh, cons, bat)
        deg = degradation_cost_eur(cmp.extra_fade_percent, bat.capacity_kwh)
        return incr + plan.total_fcr_revenue_eur - deg

    # konstantes k (Brent)
    calib = calibrate_wear_cost(price, cons, plug, bat, baseline_plan=base,
                                fcr_price_eur_per_kw_per_step=fcr, verbose=False)
    plan_c = run_rolling_year(price, cons, plug, bat,
                              wear_cost_per_kwh=calib.k_final,
                              fcr_price_eur_per_kw_per_step=fcr)
    net_c = net_of(plan_c)

    # zeitvariables k(SoC)
    k_func = make_k_of_soc(soc_grid, k_vals, bat.capacity_kwh)
    plan_s, kvec = plan_with_soc_wear(price, cons, plug, bat, k_func,
                                      fcr_price_eur_per_kw_per_step=fcr)
    net_s = net_of(plan_s)

    print(f"    konstantes k (Brent) : k={calib.k_final*100:.1f} ct  -> Netto {net_c:.1f} EUR")
    print(f"    zeitvariables k(SoC) : k={kvec.min()*100:.1f}-{kvec.max()*100:.1f} ct"
          f" -> Netto {net_s:.1f} EUR")
    check("k(SoC) ist mindestens so gut wie konstantes k",
          net_s >= net_c - 0.5, f"{net_s:.1f} vs {net_c:.1f} EUR")
    check("k(SoC)-Plan hat ein zeitvariables k (nicht konstant)",
          kvec.max() - kvec.min() > 0.01, f"Spanne {(kvec.max()-kvec.min())*100:.1f} ct")


def main():
    print("=" * 70)
    print("SCHRITT 10 TEST: zeitvariable Verschleiss-Strafe k(SoC)")
    print("=" * 70)
    soc_grid, k_vals = test_A_k_of_soc()
    test_B_compare(soc_grid, k_vals)
    print("\n" + "=" * 70)
    print("Fertig.")
    print("=" * 70)


if __name__ == "__main__":
    main()
