"""
step7_load_fcr_prices.py
========================

SCHRITT 7a: FCR-Kapazitaetspreise 2025 laden und auf die 15-Min-Zeitleiste
bringen (analog zu Schritt 2 fuer die Day-Ahead-Preise).

Datenquelle: regelleistung.net (gemeinsame Plattform der 4 deutschen TSOs).
Pro Tag gibt es 6 Ausschreibungs-Bloecke a 4 Stunden:
    NEGPOS_00_04, NEGPOS_04_08, ..., NEGPOS_20_24
"NEGPOS" = symmetrisches FCR (man muss hoch- UND runterregeln koennen).

Der Preis steht in der Spalte GERMANY_SETTLEMENTCAPACITY_PRICE_[EUR/MW] und
gilt fuer 1 MW bereitgestellte Leistung ueber den 4-Stunden-Block.

Ergebnis dieses Moduls: ein Array der Laenge TOTAL_STEPS (35040), das fuer
JEDEN 15-Min-Schritt den FCR-Preis in EUR pro MW und pro Schritt enthaelt.
Damit gilt:  FCR-Erloes in einem Schritt = angebotene_MW * preis_pro_schritt.
(Block-Preis / 16, weil 16 Viertelstunden in einem 4h-Block stecken.)
"""

from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import STEPS_PER_DAY, STEPS_PER_HOUR, TOTAL_STEPS, YEAR, YEAR_START, N_DAYS

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "fcr_prices_2025.csv"
SOURCE_FILE = DATA_DIR / "fcr_source.json"

API_URL = "https://www.regelleistung.net/apps/cpp-publisher/api/v1/download/tenders/resultsoverview"
GERMANY_PRICE_COL = "GERMANY_SETTLEMENTCAPACITY_PRICE_[EUR/MW]"

STEPS_PER_BLOCK = 4 * STEPS_PER_HOUR        # 4h-Block = 16 Viertelstunden
BLOCKS_PER_DAY = 6


# ---------------------------------------------------------------------------
# Teil 1: Rohdaten besorgen (tageweise von der API)
# ---------------------------------------------------------------------------

def _fetch_fcr_day(d: date):
    """Holt die 6 Blockpreise (Germany, EUR/MW je 4h) fuer einen Tag.
    Gibt eine Liste von 6 Werten zurueck (Block 0..5) oder None bei Fehler."""
    import requests
    params = {"productTypes": "FCR", "date": d.isoformat(), "exportFormat": "xlsx"}
    headers = {"Accept": "application/octet-stream"}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=30)
        if r.status_code != 200:
            return None
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")        # openpyxl "no default style"
            df = pd.read_excel(io.BytesIO(r.content))
    except Exception:
        return None

    if GERMANY_PRICE_COL not in df.columns or "PRODUCTNAME" not in df.columns:
        return None

    # Block-Startstunde aus dem Produktnamen lesen (NEGPOS_08_12 -> 8)
    prices = [np.nan] * BLOCKS_PER_DAY
    for _, row in df.iterrows():
        name = str(row["PRODUCTNAME"])          # z.B. "NEGPOS_08_12"
        parts = name.split("_")
        if len(parts) < 3:
            continue
        try:
            start_h = int(parts[1])
        except ValueError:
            continue
        block_idx = start_h // 4                 # 0,4,8,.. -> 0,1,2,..
        if 0 <= block_idx < BLOCKS_PER_DAY:
            # Manche Zellen sind '-' (kein dt. Wert) -> als NaN behandeln
            try:
                prices[block_idx] = float(row[GERMANY_PRICE_COL])
            except (ValueError, TypeError):
                prices[block_idx] = np.nan
    return prices


def _fetch_year(progress: bool = True) -> pd.DataFrame | None:
    """Holt alle Tage 2025. Gibt DataFrame (date, block0..block5) oder None."""
    rows = []
    d = YEAR_START
    one_day = timedelta(days=1)
    n_ok = 0
    for i in range(N_DAYS):
        prices = _fetch_fcr_day(d)
        if prices is not None and not all(np.isnan(prices)):
            rows.append([d.isoformat()] + prices)
            n_ok += 1
        else:
            rows.append([d.isoformat()] + [np.nan] * BLOCKS_PER_DAY)
        if progress and i % 30 == 0:
            print(f"    ... Tag {i:3d}/{N_DAYS} geladen (ok: {n_ok})")
        d += one_day

    if n_ok < N_DAYS * 0.5:    # weniger als die Haelfte da -> Fehlschlag
        return None
    cols = ["date"] + [f"block{b}" for b in range(BLOCKS_PER_DAY)]
    df = pd.DataFrame(rows, columns=cols)
    # vereinzelte Luecken auffuellen (Vorwert)
    df.iloc[:, 1:] = df.iloc[:, 1:].ffill().bfill()
    return df


def _synthetic_year() -> pd.DataFrame:
    """Notfall-Ersatz: realistische FCR-Blockpreise (saisonal, hoeher im Winter,
    teurer tagsueber)."""
    rng = np.random.default_rng(7)
    rows = []
    d = YEAR_START
    # typische Tagesform pro Block (EUR/MW je 4h): nachts billig, tags teuer
    base_shape = np.array([22.0, 28.0, 60.0, 45.0, 55.0, 30.0])
    for i in range(N_DAYS):
        doy = (d - YEAR_START).days
        seasonal = 1.0 + 0.4 * np.cos((doy - 15) * 2 * np.pi / 365)   # Winter teurer
        noise = rng.normal(1.0, 0.15, BLOCKS_PER_DAY)
        prices = np.maximum(base_shape * seasonal * noise, 0.0)
        rows.append([d.isoformat()] + list(prices))
        d += timedelta(days=1)
    cols = ["date"] + [f"block{b}" for b in range(BLOCKS_PER_DAY)]
    return pd.DataFrame(rows, columns=cols)


def load_fcr_blocks(force_download: bool = False) -> pd.DataFrame:
    """FCR-Blockpreise 2025 (date, block0..5 in EUR/MW je 4h). Mit Cache."""
    if CACHE_FILE.exists() and not force_download:
        return pd.read_csv(CACHE_FILE)

    print("  Lade FCR-Preise von regelleistung.net (365 Tagesabrufe, dauert ein paar Minuten)...")
    df = _fetch_year()
    source = "regelleistung.net"
    if df is None:
        print("  Download fehlgeschlagen -> nutze synthetische Ersatzdaten.")
        df = _synthetic_year()
        source = "synthetic"

    df.to_csv(CACHE_FILE, index=False)
    SOURCE_FILE.write_text(json.dumps({"source": source}))
    return df


def fcr_source() -> str:
    if SOURCE_FILE.exists():
        return json.loads(SOURCE_FILE.read_text()).get("source", "unknown")
    return "unknown"


# ---------------------------------------------------------------------------
# Teil 2: Blockpreise -> 15-Min-Zeitleiste
# ---------------------------------------------------------------------------

def fcr_blocks_to_timeline(blocks_df: pd.DataFrame) -> np.ndarray:
    """Macht aus den 6 Tagesbloecken ein Array (TOTAL_STEPS) mit dem FCR-Preis
    PRO 15-MIN-SCHRITT und pro MW (= Blockpreis / 16)."""
    out = np.zeros(TOTAL_STEPS)
    block_cols = [f"block{b}" for b in range(BLOCKS_PER_DAY)]
    for day in range(N_DAYS):
        day_blocks = blocks_df.iloc[day][block_cols].to_numpy(dtype=float)
        for b in range(BLOCKS_PER_DAY):
            price_per_step = day_blocks[b] / STEPS_PER_BLOCK   # EUR/MW pro 15min
            s = day * STEPS_PER_DAY + b * STEPS_PER_BLOCK
            e = s + STEPS_PER_BLOCK
            out[s:e] = price_per_step
    return out


def load_fcr_timeline(force_download: bool = False) -> np.ndarray:
    """FCR-Preise laden UND auf die 15-Min-Zeitleiste bringen.
    Ergebnis: EUR pro MW und pro 15-Min-Schritt (Laenge TOTAL_STEPS)."""
    blocks = load_fcr_blocks(force_download=force_download)
    return fcr_blocks_to_timeline(blocks)
