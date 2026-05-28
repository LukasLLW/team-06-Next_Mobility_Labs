"""
step9_fcr_pool.py
=================

SCHRITT 9: Die 1-MW-Mindestlosgroesse fuer FCR (Aggregator-Pool).

Am FCR-Markt darf man erst ab 1 MW bieten. Ein einzelnes Auto (z.B. 11 kW =
0,011 MW) erreicht das nie allein - es muss ueber einen AGGREGATOR-Pool mit
vielen anderen Autos buendeln (so funktioniert das Geschaeftsmodell).

Dieses Modul modelliert das:
  - Das simulierte Auto ist stellvertretend fuer einen Pool aus N identischen
    Autos. Pro Zeitschritt bietet der Pool  N * fcr_kw[t]  an.
  - FCR ist nur in den Schritten marktfaehig, in denen der Pool >= 1 MW erreicht.
    In allen anderen Schritten faellt der FCR-Erloes weg.

Daraus ergibt sich direkt die zentrale Cold-Start-Kennzahl:
  Wie viele Autos braucht der Pool mindestens, damit FCR ueberhaupt geht?
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import FCR_MIN_LOT_MW


def min_pool_size_for_fcr(fcr_kw_per_car: np.ndarray) -> int:
    """Kleinste Pool-Groesse (Anzahl identischer Autos), bei der der Pool in
    SEINEN aktiven Schritten die 1-MW-Schwelle erreicht.

    Wir nehmen die TYPISCHE angebotene Leistung pro Auto in den aktiven
    Schritten (Median der Schritte mit fcr_kw > 0)."""
    active = fcr_kw_per_car[fcr_kw_per_car > 1e-9]
    if len(active) == 0:
        return 0
    typical_kw = float(np.median(active))
    if typical_kw <= 0:
        return 0
    return math.ceil(FCR_MIN_LOT_MW * 1000.0 / typical_kw)


@dataclass
class PoolFcrResult:
    pool_size: int                    # angenommene Anzahl Autos im Pool
    marketable_fraction: float        # Anteil der FCR-Energie, die marktfaehig ist
    fcr_kw_marketable: np.ndarray     # FCR-Leistung pro Auto, NUR in marktfaehigen Schritten
    min_pool_size: int                # kritische Pool-Groesse (Cold-Start)


def apply_min_lot(fcr_kw_per_car: np.ndarray, pool_size: int) -> PoolFcrResult:
    """Wendet die 1-MW-Regel auf ein Einzelauto-FCR-Profil an.

    pool_size: Anzahl identischer Autos im Aggregator-Pool.
    Rueckgabe enthaelt das auf marktfaehige Schritte reduzierte FCR-Profil
    (pro Auto) - in Schritten, in denen der Pool < 1 MW bleibt, wird 0 gesetzt.
    """
    pool_mw = pool_size * fcr_kw_per_car / 1000.0      # Pool-Leistung je Schritt (MW)
    marketable = pool_mw >= FCR_MIN_LOT_MW             # bool: Schritt marktfaehig?

    fcr_marketable = np.where(marketable, fcr_kw_per_car, 0.0)

    total = fcr_kw_per_car.sum()
    frac = float(fcr_marketable.sum() / total) if total > 0 else 0.0

    return PoolFcrResult(
        pool_size=pool_size,
        marketable_fraction=frac,
        fcr_kw_marketable=fcr_marketable,
        min_pool_size=min_pool_size_for_fcr(fcr_kw_per_car),
    )
