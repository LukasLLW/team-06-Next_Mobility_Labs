"""
test_step1.py
=============

Testskript fuer SCHRITT 1 (Einlesen der Fahrtdaten).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step1

Das Skript:
  1) laedt Auto Nr. 1,
  2) prueft ein paar Dinge automatisch (mit klaren OK/FEHLER-Meldungen),
  3) druckt einen lesbaren Tagesablauf fuer den 1. Januar, damit ihr mit
     eigenen Augen seht, dass Fahren/Anstecken/Verbrauch korrekt landen.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from engine.config import STEP_MINUTES, STEPS_PER_DAY, TOTAL_STEPS
from engine.step1_load_trips import load_car_timeline


# Pfad zu den Demodaten (relativ zum Repo-Hauptordner)
DEMO_DIR = Path(__file__).resolve().parents[2] / "demodata"
CAR_CSV = DEMO_DIR / "fahrtdaten_2025_01.csv"


def check(name: str, condition: bool, detail: str = "") -> None:
    """Kleine Hilfsfunktion: druckt OK oder FEHLER."""
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def step_to_clock(step_in_day: int) -> str:
    """Schritt-Nummer im Tag (0..95) -> Uhrzeit-String wie '07:30'."""
    minutes = step_in_day * STEP_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def main() -> None:
    print("=" * 70)
    print("SCHRITT 1 TEST: Fahrtdaten einlesen")
    print("=" * 70)
    print(f"Datei: {CAR_CSV.name}\n")

    trips, tl = load_car_timeline(CAR_CSV)

    # --- Automatische Pruefungen -------------------------------------------
    print("Automatische Pruefungen:")

    # 365 Tage * 3 Fahrten = 1095 Fahrten erwartet
    check("Anzahl Fahrten == 1095", len(trips) == 1095, f"gefunden: {len(trips)}")

    # Arrays haben die richtige Laenge
    check("Array-Laenge == TOTAL_STEPS", len(tl.consumption_kwh) == TOTAL_STEPS,
          f"{len(tl.consumption_kwh)} == {TOTAL_STEPS}")

    # Energieerhaltung: Summe der Zeitleiste == Summe der CSV-Verbraeuche
    csv_total = sum(t.consumed_kwh for t in trips)
    grid_total = tl.consumption_kwh.sum()
    check("Verbrauch bleibt erhalten (CSV-Summe == Zeitleisten-Summe)",
          abs(csv_total - grid_total) < 1e-6,
          f"CSV={csv_total:.2f} kWh, Zeitleiste={grid_total:.2f} kWh")

    # Erwarteter Tagesverbrauch laut Generator: 4.5 + 1.2 + 5.0 = 10.7 kWh
    expected_daily = 4.5 + 1.2 + 5.0
    expected_year = expected_daily * 365
    check("Jahresverbrauch == 10.7 kWh/Tag * 365",
          abs(csv_total - expected_year) < 1e-6,
          f"erwartet {expected_year:.1f} kWh, ist {csv_total:.1f} kWh")

    # Man kann nicht gleichzeitig fahren UND angesteckt sein
    both = np.logical_and(tl.driving, tl.plugged_in).sum()
    check("Nie gleichzeitig fahren und angesteckt", both == 0,
          f"{both} Schritte mit beidem")

    # --- Kennzahlen --------------------------------------------------------
    print("\nKennzahlen (uebers ganze Jahr):")
    drive_h = tl.driving.sum() * (STEP_MINUTES / 60)
    plug_h = tl.plugged_in.sum() * (STEP_MINUTES / 60)
    idle_unplugged_h = (~tl.driving & ~tl.plugged_in).sum() * (STEP_MINUTES / 60)
    print(f"  Stunden fahrend          : {drive_h:8.1f} h  ({drive_h/365:.2f} h/Tag)")
    print(f"  Stunden angesteckt (V2G) : {plug_h:8.1f} h  ({plug_h/365:.2f} h/Tag)")
    print(f"  Stunden geparkt o. Stecker: {idle_unplugged_h:8.1f} h  ({idle_unplugged_h/365:.2f} h/Tag)")

    # --- Lesbarer Tagesablauf fuer den 1. Januar ---------------------------
    print("\nTagesablauf 01.01.2025 (jeder 15-Min-Schritt):")
    print("  Zeit   | faehrt | Stecker | Verbrauch")
    print("  -------+--------+---------+----------")
    for step_in_day in range(STEPS_PER_DAY):
        t = step_in_day  # 1. Januar = Schritte 0..95
        drv = "  X   " if tl.driving[t] else "      "
        plg = "   X   " if tl.plugged_in[t] else "       "
        cons = tl.consumption_kwh[t]
        cons_str = f"{cons:.2f} kWh" if cons > 0 else ""
        # Nur "interessante" Zeilen + alle 2h einen Marker, damit es kompakt bleibt
        interesting = tl.driving[t] or cons > 0 or (step_in_day % 8 == 0)
        if interesting:
            print(f"  {step_to_clock(step_in_day)}  |{drv}  |{plg}  | {cons_str}")

    print("\nLesehilfe:")
    print("  - Morgens 07:30-08:15 faehrt das Auto (4.5 kWh), danach NICHT angesteckt.")
    print("  - Mittags 12:00-12:30 faehrt es (1.2 kWh), danach NICHT angesteckt.")
    print("  - Abends 17:30-18:15 faehrt es (5.0 kWh), danach ANGESTECKT (charger=True).")
    print("  - Also: Stecker-Fenster = abends 18:15 bis morgens 07:30 (ueber Nacht).")
    print("=" * 70)


if __name__ == "__main__":
    main()
