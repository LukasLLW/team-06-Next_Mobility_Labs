"""
step1_load_trips.py
===================

SCHRITT 1: Fahrtdaten einlesen und in eine Zeitleiste umwandeln.

Es gibt zwei Funktionen:

  1) load_trips(csv_path)
        Liest EINE Auto-CSV (z.B. fahrtdaten_2025_01.csv) ein und gibt
        die einzelnen Fahrten als saubere Liste zurueck.

  2) build_timeline(trips)
        Wandelt diese Fahrten in drei numpy-Arrays um, die fuer JEDEN
        15-Minuten-Schritt des Jahres einen Wert haben:

          consumption_kwh[t]  -> wie viel kWh in Schritt t gefahren wird
          driving[t]          -> True, wenn das Auto in Schritt t faehrt
          plugged_in[t]       -> True, wenn das Auto in Schritt t am
                                  Ladegeraet haengt (V2G moeglich)

        Laenge jedes Arrays = TOTAL_STEPS (= 35040 fuer 2025).

Die Idee dahinter (Zustand zwischen den Fahrten):
  Das Feld `charger_true_false` gehoert zu einer Fahrt und bedeutet:
  "Ist das Auto NACH dieser Fahrt am Ladegeraet angesteckt?"
  -> Nach einer Fahrt mit charger=True ist das Auto angesteckt, bis die
     naechste Fahrt beginnt.
  -> Nach charger=False steht es geparkt, aber NICHT angesteckt.
  Vor der allerersten Fahrt des Jahres nehmen wir an: angesteckt
  (das Auto stand ueber Nacht zu Hause an der Wallbox).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from .config import STEPS_PER_DAY, STEP_HOURS, TOTAL_STEPS, YEAR_START


# ---------------------------------------------------------------------------
# Teil 1: CSV einlesen
# ---------------------------------------------------------------------------

@dataclass
class Trip:
    """Eine einzelne Fahrt aus der CSV."""
    start: datetime          # Startzeitpunkt
    end: datetime            # Endzeitpunkt
    consumed_kwh: float      # verbrauchte Energie
    plugged_after: bool      # am Ladegeraet NACH dieser Fahrt?


def load_trips(csv_path: str | Path) -> list[Trip]:
    """Liest eine Auto-CSV und gibt eine Liste von Trip-Objekten zurueck."""
    csv_path = Path(csv_path)
    trips: list[Trip] = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            start = datetime.strptime(row["time_start"], "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(row["time_end"], "%Y-%m-%d %H:%M:%S")
            kwh = float(row["consumed_kWh"])
            # "True"/"False" als Text -> echtes bool
            plugged = row["charger_true_false"].strip().lower() == "true"
            trips.append(Trip(start=start, end=end, consumed_kwh=kwh,
                              plugged_after=plugged))

    return trips


# ---------------------------------------------------------------------------
# Teil 2: Hilfsfunktion - Zeitpunkt -> (fraktionaler) Schritt-Index
# ---------------------------------------------------------------------------

def _to_step_float(ts: datetime) -> float:
    """Rechnet einen Zeitpunkt in einen (moeglicherweise gebrochenen)
    Schritt-Index um, gemessen ab dem 1. Januar 00:00.

    Beispiel (15-Min-Schritte):
      01.01. 00:00 -> 0.0
      01.01. 07:30 -> 30.0     (7.5 h * 4 Schritte/h)
      01.01. 08:15 -> 33.0
      02.01. 00:00 -> 96.0
    """
    day_index = (ts.date() - YEAR_START).days       # 0 fuer 1. Jan, 1 fuer 2. Jan, ...
    minutes_into_day = ts.hour * 60 + ts.minute + ts.second / 60.0
    step_in_day = minutes_into_day / 15.0            # 15 Min pro Schritt
    return day_index * STEPS_PER_DAY + step_in_day


# ---------------------------------------------------------------------------
# Teil 3: Zeitleiste bauen
# ---------------------------------------------------------------------------

@dataclass
class Timeline:
    """Die fertige Zeitleiste fuers ganze Jahr (alle Arrays gleich lang)."""
    consumption_kwh: np.ndarray   # float, kWh pro Schritt durch Fahren
    driving: np.ndarray           # bool, faehrt das Auto in diesem Schritt?
    plugged_in: np.ndarray        # bool, am Ladegeraet in diesem Schritt?


def build_timeline(trips: list[Trip]) -> Timeline:
    """Wandelt Fahrten in die drei Jahres-Arrays um (siehe Modul-Doku)."""
    consumption = np.zeros(TOTAL_STEPS, dtype=float)
    driving = np.zeros(TOTAL_STEPS, dtype=bool)
    plugged = np.zeros(TOTAL_STEPS, dtype=bool)

    # --- 3a) Fahrten eintragen: Verbrauch verteilen + driving markieren -----
    for trip in trips:
        s = _to_step_float(trip.start)   # z.B. 30.0
        e = _to_step_float(trip.end)     # z.B. 33.0
        total_len = e - s                # Laenge der Fahrt in Schritten (z.B. 3.0)
        if total_len <= 0:
            continue                     # leere/ungueltige Fahrt ueberspringen

        # Ueber alle Schritte gehen, die diese Fahrt beruehrt
        first = int(np.floor(s))
        last = int(np.ceil(e))           # exklusiv
        for t in range(first, last):
            if t < 0 or t >= TOTAL_STEPS:
                continue
            # Wie gross ist die Ueberlappung von Schritt t mit der Fahrt?
            overlap = min(t + 1, e) - max(t, s)   # in Schritten (0..1)
            if overlap > 0:
                # Verbrauch anteilig zur Ueberlappung verteilen
                consumption[t] += trip.consumed_kwh * (overlap / total_len)
                driving[t] = True

    # --- 3b) Ladestatus zwischen den Fahrten setzen -------------------------
    # Annahme: vor der ersten Fahrt ist das Auto angesteckt.
    state_plugged = True

    # Wir gehen die Fahrten zeitlich sortiert durch. Zwischen dem Ende einer
    # Fahrt und dem Beginn der naechsten gilt der "plugged_after"-Status der
    # gerade beendeten Fahrt.
    trips_sorted = sorted(trips, key=lambda tr: tr.start)

    # Zeiger auf den ersten Schritt, der noch keinen Status hat
    prev_end_step = 0
    for trip in trips_sorted:
        s = int(np.floor(_to_step_float(trip.start)))
        e = int(np.ceil(_to_step_float(trip.end)))

        # Schritte VOR dieser Fahrt (seit Ende der letzten Fahrt) bekommen den
        # aktuellen state_plugged - aber nur, solange nicht gefahren wird.
        for t in range(max(prev_end_step, 0), min(s, TOTAL_STEPS)):
            if not driving[t]:
                plugged[t] = state_plugged

        # Waehrend der Fahrt: nicht angesteckt (faehrt ja)
        # (driving[t] ist dort True, plugged bleibt False)

        # Nach dieser Fahrt gilt ihr eigener charger-Status
        state_plugged = trip.plugged_after
        prev_end_step = e

    # Schritte nach der letzten Fahrt bis Jahresende
    for t in range(max(prev_end_step, 0), TOTAL_STEPS):
        if not driving[t]:
            plugged[t] = state_plugged

    return Timeline(consumption_kwh=consumption, driving=driving, plugged_in=plugged)


# ---------------------------------------------------------------------------
# Komfort: beides in einem Aufruf
# ---------------------------------------------------------------------------

def load_car_timeline(csv_path: str | Path) -> tuple[list[Trip], Timeline]:
    """CSV laden UND Zeitleiste bauen. Gibt (trips, timeline) zurueck."""
    trips = load_trips(csv_path)
    timeline = build_timeline(trips)
    return trips, timeline
