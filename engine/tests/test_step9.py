"""
test_step9.py
=============

Testskript fuer SCHRITT 9 (EoL-Kostenmodell + 1-MW-FCR-Pool).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step9

Teil A: End-of-Life-Kostenmodell (EoL-Schwelle macht jede %-Mehralterung teurer).
Teil B: 1-MW-Mindestlosgroesse - kritische Pool-Groesse und marktfaehiger Anteil.

Laufzeit: ca. 1 Minute (ein Optimierer-Lauf fuer ein echtes FCR-Profil).
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from engine import config
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline
from engine.step3_battery import BatteryModel
from engine.step4_optimizer import run_rolling_year
from engine.step6_net_profit import degradation_cost_eur
from engine.step7_load_fcr_prices import load_fcr_timeline
from engine.step9_fcr_pool import apply_min_lot, min_pool_size_for_fcr

DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def test_A_eol_model():
    print("\nTest A: End-of-Life-Kostenmodell")
    cap, cost = 75.0, 160.0      # 75 kWh, 160 EUR/kWh -> 12000 EUR Pack
    extra_fade = 1.0             # 1 % Mehralterung pro Jahr

    # linear (EoL = 100 %): 1 % von 12000 EUR = 120 EUR
    lin = degradation_cost_eur(extra_fade, cap, cost, eol_loss_pct=100.0)
    # EoL bei 20 %: 5x teurer
    eol = degradation_cost_eur(extra_fade, cap, cost, eol_loss_pct=20.0)

    check("lineares Modell: 1 % -> 120 EUR", abs(lin - 120.0) < 1e-6, f"{lin:.1f} EUR")
    check("EoL-Modell (20 %) ist 5x teurer", abs(eol - 5 * lin) < 1e-6,
          f"{eol:.1f} EUR (= 5 x {lin:.1f})")
    print(f"       aktuelle config-Schwelle: EoL bei {config.BATTERY_EOL_LOSS_PCT:.0f} % Verlust")


def test_B_min_lot():
    print("\nTest B: 1-MW-Mindestlosgroesse (Aggregator-Pool)")
    trips, tl = load_car_timeline(CAR_CSV)
    price = load_price_timeline() / 1000.0
    fcr = load_fcr_timeline() / 1000.0
    bat = BatteryModel()

    print("    Optimiere ein FCR-Profil (1 Lauf)...")
    t0 = time.time()
    plan = run_rolling_year(price, tl.consumption_kwh, tl.plugged_in, bat,
                            wear_cost_per_kwh=0.02, fcr_price_eur_per_kw_per_step=fcr)
    print(f"      fertig ({time.time()-t0:.0f}s)")

    fcr_kw = plan.fcr_kw
    n_min = min_pool_size_for_fcr(fcr_kw)
    max_offered = fcr_kw.max()
    print(f"    max. angebotene FCR-Leistung pro Auto: {max_offered:.1f} kW")
    print(f"    kritische Pool-Groesse fuer 1 MW: {n_min} Autos (Cold-Start-Schwelle)")

    check("kritische Pool-Groesse plausibel (~1000/11 kW ~ 91)",
          80 <= n_min <= 110, f"{n_min} Autos")

    # Pool zu klein vs gross genug
    small = apply_min_lot(fcr_kw, pool_size=20)
    big = apply_min_lot(fcr_kw, pool_size=n_min + 10)

    print(f"\n    Pool mit 20 Autos : marktfaehiger FCR-Anteil = {small.marketable_fraction*100:.0f} %")
    print(f"    Pool mit {n_min+10} Autos: marktfaehiger FCR-Anteil = {big.marketable_fraction*100:.0f} %")

    check("Pool mit 20 Autos erreicht 1 MW NICHT (0 % marktfaehig)",
          small.marketable_fraction < 0.01, f"{small.marketable_fraction*100:.1f} %")
    check("Pool ueber kritischer Groesse ist (fast) voll marktfaehig",
          big.marketable_fraction > 0.9, f"{big.marketable_fraction*100:.1f} %")

    print("\n  Geschaeftliche Einsicht (Cold-Start):")
    print(f"  - Mit < {n_min} angesteckten Autos kann der Pool kein FCR anbieten -> 0 Erloes.")
    print(f"  - Die ersten ~{n_min} Kunden 'finanzieren' also die Markteintrittsschwelle.")
    print("  - Genau das Henne-Ei-Problem aus dem Challenge-Dokument.")


def main():
    print("=" * 72)
    print("SCHRITT 9 TEST: EoL-Kostenmodell + 1-MW-FCR-Pool")
    print("=" * 72)
    test_A_eol_model()
    test_B_min_lot()
    print("\n" + "=" * 72)
    print("Fertig.")
    print("=" * 72)


if __name__ == "__main__":
    main()
