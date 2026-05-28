"""
step2_load_prices.py
====================

SCHRITT 2: Day-Ahead-Strompreise 2025 laden und auf DIESELBE Zeitleiste
bringen wie die Fahrtdaten aus Schritt 1.

Ergebnis ist ein numpy-Array `price_eur_mwh` mit GENAU TOTAL_STEPS (=35040)
Eintraegen - also fuer jeden 15-Minuten-Schritt ein Preis. Damit passen
Preise und Fahrten Schritt fuer Schritt zusammen.

Drei Funktionen:

  1) load_prices_hourly()
        Besorgt die stuendlichen Day-Ahead-Preise fuer 2025 (in EUR/MWh).
        Reihenfolge: lokale Cache-Datei -> SMARD.de herunterladen ->
        (Notfall) synthetische, aber realistische Ersatzdaten.

  2) prices_to_timeline(hourly_df)
        Breitet die Stundenpreise auf das 15-Minuten-Raster aus
        (jeder Stundenpreis gilt fuer seine 4 Viertelstunden) und richtet
        sie exakt an unserem 96-Schritte-pro-Tag-Raster aus.

  3) load_price_timeline()
        Macht beides in einem Aufruf -> gibt das fertige Array zurueck.

Warum die Zeitausrichtung knifflig ist:
  - Unsere Fahrt-Zeitleiste behandelt jeden Tag als 96 Schritte (naive
    Wanduhrzeit, ohne Sommer-/Winterzeit).
  - Die SMARD-Preise sind dagegen zeitzonenbehaftet (Europe/Berlin) und
    enthalten die echte Zeitumstellung: im Maerz fehlt die Stunde 02:00,
    im Oktober gibt es 02:00 doppelt.
  Trick: Wir bauen einen NAIVEN 15-Minuten-Index ueber 2025. Naiv = ohne
  Zeitzone, also auch ohne DST -> der hat automatisch exakt 35040 Eintraege.
  Auf diesen Index legen wir die Preise (per "forward fill"), so dass die
  fehlende Maerz-Stunde mit dem Nachbarwert aufgefuellt und die doppelte
  Oktober-Stunde entschaerft wird.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from .config import TOTAL_STEPS, YEAR

# --- Wo liegt die Cache-Datei? ---------------------------------------------
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "smard_dayahead_2025.csv"
SOURCE_FILE = DATA_DIR / "price_source.json"

# SMARD-Kennungen fuer den Day-Ahead-Grosshandelspreis Deutschland/Luxemburg
SMARD_FILTER_DAYAHEAD = 4169
SMARD_REGION = "DE-LU"


# ---------------------------------------------------------------------------
# Teil 1: Stundenpreise besorgen
# ---------------------------------------------------------------------------

def _fetch_smard() -> pd.DataFrame | None:
    """Versucht, die Stundenpreise 2025 von SMARD.de zu laden.
    Gibt None zurueck, wenn etwas schiefgeht (dann nutzen wir Ersatzdaten)."""
    try:
        import requests
    except ImportError:
        return None

    base = "https://www.smard.de/app/chart_data"
    idx_url = f"{base}/{SMARD_FILTER_DAYAHEAD}/{SMARD_REGION}/index_hour.json"
    try:
        idx = requests.get(idx_url, timeout=20).json()
    except Exception:
        return None

    timestamps = idx.get("timestamps", [])
    if not timestamps:
        return None

    # SMARD liefert die Daten in Wochenpaketen (indexiert nach Montag-Zeitstempel).
    # Wir holen grosszuegig alle Pakete rund um 2025.
    start_ms = int(pd.Timestamp("2024-12-01", tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp("2026-01-15", tz="UTC").timestamp() * 1000)

    rows = []
    for ts in timestamps:
        if ts < start_ms or ts > end_ms:
            continue
        url = (f"{base}/{SMARD_FILTER_DAYAHEAD}/{SMARD_REGION}/"
               f"{SMARD_FILTER_DAYAHEAD}_{SMARD_REGION}_hour_{ts}.json")
        try:
            week = requests.get(url, timeout=20).json()
        except Exception:
            return None
        for item in week.get("series", []):
            if len(item) >= 2 and item[1] is not None:
                rows.append((item[0], item[1]))

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=["ts_ms", "price_eur_mwh"])
    df["timestamp"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True
                                     ).dt.tz_convert("Europe/Berlin")
    df = df.drop(columns="ts_ms").set_index("timestamp").sort_index()
    df = df[(df.index >= f"{YEAR}-01-01") & (df.index < f"{YEAR + 1}-01-01")]
    return df


def _synthetic() -> pd.DataFrame:
    """Notfall-Ersatz: realistische, aber kuenstliche Stundenpreise 2025.

    Enthaelt die typischen Muster: Morgen-/Abendspitze, Solar-Delle mittags,
    guenstigere Wochenenden, teurer im Winter, gelegentlich negative Preise.
    """
    rng = np.random.default_rng(42)
    idx = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h",
                        tz="Europe/Berlin")
    n = len(idx)
    hours = idx.hour.to_numpy()
    doy = idx.dayofyear.to_numpy()
    wd = idx.weekday.to_numpy()

    base = 90.0
    daily = (18 * np.cos((hours - 19) * math.pi / 12)
             + 10 * np.cos((hours - 8) * math.pi / 12)
             - 22 * np.exp(-((hours - 13) ** 2) / 8))
    seasonal = 30 * np.cos((doy - 15) * 2 * math.pi / 365)
    weekend = np.where(wd >= 5, -12.0, 0.0)
    noise = rng.normal(0, 8, n)
    surplus = np.zeros(n)
    mask = (wd >= 5) & (hours >= 11) & (hours <= 15)
    surplus[mask] += rng.normal(-40, 25, mask.sum())

    price = base + daily + seasonal + weekend + noise + surplus
    return pd.DataFrame({"price_eur_mwh": price}, index=idx)


def load_prices_hourly(force_download: bool = False) -> pd.DataFrame:
    """Stundenpreise 2025 als DataFrame (tz-aware Europe/Berlin, EUR/MWh).

    Nutzt die Cache-Datei, falls vorhanden. Sonst Download von SMARD, sonst
    synthetische Ersatzdaten. Schreibt das Ergebnis in den Cache.
    """
    if CACHE_FILE.exists() and not force_download:
        df = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"], index_col="timestamp")
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("Europe/Berlin")
        return df

    df = _fetch_smard()
    source = "smard"
    if df is None or len(df) < 8000:
        df = _synthetic()
        source = "synthetic"

    out = df.copy()
    out.index.name = "timestamp"
    out.to_csv(CACHE_FILE)
    SOURCE_FILE.write_text(json.dumps({"source": source, "rows": len(df)}))
    return df


def price_source() -> dict:
    """Woher stammen die zuletzt geladenen Preise? (fuer Anzeige im UI)"""
    if SOURCE_FILE.exists():
        return json.loads(SOURCE_FILE.read_text())
    return {"source": "unknown", "rows": 0}


# ---------------------------------------------------------------------------
# Teil 2: Stundenpreise -> 15-Minuten-Zeitleiste (35040 Schritte)
# ---------------------------------------------------------------------------

def prices_to_timeline(hourly_df: pd.DataFrame) -> np.ndarray:
    """Breitet die Stundenpreise auf das 15-Min-Raster aus und richtet sie an
    unserem 96-Schritte-pro-Tag-Raster aus. Gibt ein Array der Laenge
    TOTAL_STEPS (EUR/MWh) zurueck."""

    # 1) Stundenpreise von zeitzonenbehaftet -> naive lokale Zeit.
    #    Bei der Oktober-Umstellung gibt es 02:00 doppelt -> ersten Wert behalten.
    s = hourly_df["price_eur_mwh"].copy()
    s.index = s.index.tz_localize(None)            # Zeitzone "abstreifen"
    s = s[~s.index.duplicated(keep="first")]       # Duplikate (Okt) entfernen
    s = s.sort_index()

    # 2) Ziel-Index: naiver 15-Minuten-Takt ueber ganz 2025.
    #    Weil naiv (keine Zeitzone), gibt es kein DST -> exakt 35040 Eintraege.
    target = pd.date_range(f"{YEAR}-01-01 00:00", f"{YEAR}-12-31 23:45",
                           freq=f"{15}min")
    assert len(target) == TOTAL_STEPS, (
        f"Ziel-Index hat {len(target)} statt {TOTAL_STEPS} Eintraege")

    # 3) Stundenpreise auf das 15-Min-Raster legen.
    #    'ffill' = jeder Viertelstunden-Schritt erbt den Preis seiner Stunde;
    #    die im Maerz fehlende Stunde wird vom Vorwert aufgefuellt.
    aligned = s.reindex(target, method="ffill")

    # Sicherheitsnetz: falls ganz am Anfang noch Luecken sind, rueckwaerts fuellen.
    aligned = aligned.bfill()

    return aligned.to_numpy(dtype=float)


# ---------------------------------------------------------------------------
# Komfort
# ---------------------------------------------------------------------------

def load_price_timeline(force_download: bool = False) -> np.ndarray:
    """Stundenpreise laden UND auf die 15-Min-Zeitleiste bringen.
    Gibt ein Array der Laenge TOTAL_STEPS (EUR/MWh) zurueck."""
    hourly = load_prices_hourly(force_download=force_download)
    return prices_to_timeline(hourly)
