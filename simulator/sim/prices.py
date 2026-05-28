"""Day-ahead electricity price loader.

Tries SMARD.de API; falls back to a synthetic but realistic 2025 hourly
price series with daily, weekly and seasonal patterns.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE = DATA_DIR / "smard_dayahead_2025.csv"

SMARD_FILTER_DAYAHEAD = 4169
SMARD_REGION = "DE-LU"


def _fetch_smard_2025() -> pd.DataFrame | None:
    """Try to download SMARD day-ahead prices for 2025. Return None on failure."""
    try:
        import requests
    except ImportError:
        return None

    base = "https://www.smard.de/app/chart_data"
    idx_url = f"{base}/{SMARD_FILTER_DAYAHEAD}/{SMARD_REGION}/index_hour.json"
    try:
        idx = requests.get(idx_url, timeout=15).json()
    except Exception:
        return None
    timestamps = idx.get("timestamps", [])
    if not timestamps:
        return None

    # SMARD groups data into weekly buckets indexed by the Monday timestamp (ms).
    # Pull every bucket whose Monday falls within 2025.
    # SMARD week buckets are indexed by Monday 00:00 UTC. Expand range generously
    # so we capture the week containing 2025-01-01 (Mon 2024-12-23 or 2024-12-30).
    start_ms = int(pd.Timestamp("2024-12-01", tz="UTC").timestamp() * 1000)
    end_ms = int(pd.Timestamp("2026-01-15", tz="UTC").timestamp() * 1000)
    rows = []
    for ts in timestamps:
        if ts < start_ms or ts > end_ms:
            continue
        url = f"{base}/{SMARD_FILTER_DAYAHEAD}/{SMARD_REGION}/{SMARD_FILTER_DAYAHEAD}_{SMARD_REGION}_hour_{ts}.json"
        try:
            week = requests.get(url, timeout=15).json()
        except Exception:
            return None
        for item in week.get("series", []):
            if len(item) >= 2 and item[1] is not None:
                rows.append((item[0], item[1]))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["ts_ms", "price_eur_mwh"])
    df["timestamp"] = pd.to_datetime(df["ts_ms"], unit="ms", utc=True).dt.tz_convert("Europe/Berlin")
    df = df.drop(columns="ts_ms").set_index("timestamp").sort_index()
    df = df[(df.index >= "2025-01-01") & (df.index < "2026-01-01")]
    return df


def _synthetic_2025() -> pd.DataFrame:
    """Generate a realistic synthetic 2025 day-ahead price series in €/MWh.

    Patterns built in:
      * Daily peaks ~08:00 and ~18-20:00, troughs ~13-15:00 (solar) and ~03:00.
      * Weekend lower demand → lower prices.
      * Seasonal: winter prices ~1.4x summer.
      * Occasional negative prices on sunny weekends.
    """
    rng = np.random.default_rng(42)
    idx = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h", tz="Europe/Berlin")
    n = len(idx)
    hours = idx.hour.to_numpy()
    days_of_year = idx.dayofyear.to_numpy()
    weekday = idx.weekday.to_numpy()

    base = 90.0  # €/MWh baseline

    # Daily shape: morning + evening peaks, midday trough
    daily = (
        18 * np.cos((hours - 19) * math.pi / 12)            # evening peak ~19h
        + 10 * np.cos((hours - 8) * math.pi / 12)           # morning peak ~8h
        - 22 * np.exp(-((hours - 13) ** 2) / 8)             # solar midday dip
    )

    # Seasonal: winter expensive, summer cheap
    seasonal = 30 * np.cos((days_of_year - 15) * 2 * math.pi / 365)

    # Weekend discount
    weekend = np.where(weekday >= 5, -12.0, 0.0)

    # Noise
    noise = rng.normal(0, 8, n)

    # Renewable surplus spikes: occasional negative-price hours on weekend midday
    surplus = np.zeros(n)
    surplus_mask = (weekday >= 5) & (hours >= 11) & (hours <= 15)
    surplus[surplus_mask] += rng.normal(-40, 25, surplus_mask.sum())

    price = base + daily + seasonal + weekend + noise + surplus
    return pd.DataFrame({"price_eur_mwh": price}, index=idx)


def load_prices(force_synthetic: bool = False) -> pd.DataFrame:
    """Load 2025 hourly day-ahead prices. Cached on disk."""
    if CACHE_FILE.exists() and not force_synthetic:
        df = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"], index_col="timestamp")
        df.index = pd.to_datetime(df.index, utc=True).tz_convert("Europe/Berlin")
        return df

    df = None if force_synthetic else _fetch_smard_2025()
    source = "smard"
    if df is None:
        df = _synthetic_2025()
        source = "synthetic"

    df.attrs["source"] = source
    out = df.copy()
    out.index.name = "timestamp"
    out.to_csv(CACHE_FILE)
    # Mark source in a sidecar so the UI can show it
    (DATA_DIR / "price_source.json").write_text(json.dumps({"source": source}))
    return df


def price_source() -> str:
    f = DATA_DIR / "price_source.json"
    if f.exists():
        return json.loads(f.read_text()).get("source", "unknown")
    return "unknown"


if __name__ == "__main__":
    df = load_prices()
    print(f"Loaded {len(df)} hours from {price_source()}")
    print(df.describe())
