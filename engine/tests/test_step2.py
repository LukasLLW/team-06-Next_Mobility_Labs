"""
test_step2.py
=============

Testskript fuer SCHRITT 2 (Day-Ahead-Preise auf die Zeitleiste bringen).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step2

Beim ersten Mal kann der SMARD-Download ca. 30 Sekunden dauern; danach liegt
eine Cache-Datei in engine/data/ und es geht sofort.

Das Skript:
  1) laedt die Stundenpreise,
  2) baut die 15-Min-Zeitleiste,
  3) prueft Laenge, Ausrichtung und Plausibilitaet (mit OK/FEHLER-Meldungen),
  4) druckt den Preisverlauf am 1. Januar, damit ihr seht, dass jeder
     Stundenpreis genau auf seine 4 Viertelstunden verteilt wurde.
"""

from __future__ import annotations

import numpy as np

from engine.config import STEP_MINUTES, STEPS_PER_DAY, STEPS_PER_HOUR, TOTAL_STEPS
from engine.step2_load_prices import (
    load_prices_hourly,
    prices_to_timeline,
    price_source,
)


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def step_to_clock(step_in_day: int) -> str:
    minutes = step_in_day * STEP_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def main() -> None:
    print("=" * 70)
    print("SCHRITT 2 TEST: Day-Ahead-Preise auf die Zeitleiste bringen")
    print("=" * 70)

    print("Lade Stundenpreise (evtl. Download beim ersten Mal)...")
    hourly = load_prices_hourly()
    src = price_source()
    print(f"Quelle: {src.get('source')}  (Stunden geladen: {len(hourly)})\n")

    prices = prices_to_timeline(hourly)

    # --- Automatische Pruefungen -------------------------------------------
    print("Automatische Pruefungen:")

    check("Stundenpreise ~ 8760 (ganzes Jahr)", len(hourly) >= 8000,
          f"{len(hourly)} Stunden")

    check("Zeitleisten-Laenge == TOTAL_STEPS", len(prices) == TOTAL_STEPS,
          f"{len(prices)} == {TOTAL_STEPS}")

    check("Keine fehlenden Werte (NaN)", not np.isnan(prices).any(),
          f"{int(np.isnan(prices).sum())} NaN")

    # Ausrichtung: die ersten 4 Schritte (00:00-01:00 am 1. Jan) muessen alle
    # denselben Preis haben = der erste Stundenpreis.
    first_hour_price = hourly["price_eur_mwh"].iloc[0]
    first_four = prices[:STEPS_PER_HOUR]
    check("Erste 4 Viertelstunden == erster Stundenpreis",
          np.allclose(first_four, first_hour_price),
          f"4x {first_four[0]:.2f} vs Stunde {first_hour_price:.2f}")

    # Mittelwert der 15-Min-Zeitleiste ~ Mittelwert der Stundenpreise
    # (kleine Abweichung durch DST-Auffuellung ist ok).
    mean_hourly = hourly["price_eur_mwh"].mean()
    mean_steps = prices.mean()
    check("Mittelwert bleibt ~gleich (15-Min vs Stunden)",
          abs(mean_hourly - mean_steps) < 1.0,
          f"Stunden={mean_hourly:.2f}, 15-Min={mean_steps:.2f} EUR/MWh")

    # --- Kennzahlen --------------------------------------------------------
    print("\nKennzahlen (EUR/MWh ueber 2025):")
    print(f"  Mittel : {prices.mean():8.2f}")
    print(f"  Minimum: {prices.min():8.2f}   (negative Preise = Stromueberschuss)")
    print(f"  Maximum: {prices.max():8.2f}")
    neg = (prices < 0).sum()
    print(f"  Schritte mit negativem Preis: {neg}  ({neg / TOTAL_STEPS * 100:.1f} %)")
    print("  Umrechnung: 1 EUR/MWh = 0,1 ct/kWh  ->  Mittel ~ "
          f"{prices.mean() / 10:.1f} ct/kWh")

    # --- Preisverlauf am 1. Januar -----------------------------------------
    print("\nPreisverlauf 01.01.2025 (jede 2. Stunde, alle 4 Viertelstunden):")
    print("  Zeit   | EUR/MWh")
    print("  -------+--------")
    for step_in_day in range(STEPS_PER_DAY):
        # nur volle Stunden + ihre Viertelstunden zeigen, aber kompakt:
        if step_in_day % STEPS_PER_HOUR == 0 and (step_in_day // STEPS_PER_HOUR) % 2 == 0:
            # ganze Stunde -> zeige die 4 Viertelstunden dieser Stunde
            block = prices[step_in_day:step_in_day + STEPS_PER_HOUR]
            for k, p in enumerate(block):
                print(f"  {step_to_clock(step_in_day + k)}  | {p:7.2f}")

    print("\nLesehilfe:")
    print("  - Innerhalb einer Stunde sind alle 4 Viertelstunden gleich")
    print("    (Day-Ahead-Preise sind stuendlich -> wir breiten sie aus).")
    print("  - Negative Preise bedeuten: es gibt Stromueberschuss, das Laden")
    print("    wuerde dann sogar Geld bringen -> ideal fuer V2G.")
    print("=" * 70)


if __name__ == "__main__":
    main()
