"""
step8_calibrate_wear.py
=======================

SCHRITT 8: Den Verschleiss-Strafterm k bestimmen, der den Netto-Gewinn
MAXIMIERT - per echter 1-D-Optimierung (goldener Schnitt / Brent).

Warum nicht Fixpunkt, nicht Sweep?
  - Ein frueherer Fixpunkt "k = Durchschnittskosten(k)" loeste die FALSCHE
    Gleichung: bei konvexer Alterung gibt es dafuer keinen stabilen Fixpunkt
    (die Iteration kollabiert).
  - Ein Sweep (festes Raster) ist stumpf und ineffizient.
  - Das richtige Ziel ist: argmax_k  Netto(k). Das ist eine 1-D-Optimierung.
    Netto(k) ist unimodal (k=0: viel Arbitrage + viel Verschleiss; k gross:
    nur FCR), daher findet Brent das Maximum gezielt in ~10 Auswertungen.

Jede Auswertung Netto(k) kostet einen Optimierer-Lauf + eine KIT-Bewertung -
deshalb am besten auf einem kurzen Zeitraum kalibrieren (siehe run_demo --days).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize_scalar

from . import config
from .step3_battery import BatteryModel
from .step4_optimizer import run_rolling_year, YearPlan
from .step5_degradation_kit import compare_baseline_vs_v2g
from .step6_net_profit import degradation_cost_eur


@dataclass
class CalibrationResult:
    k_final: float                   # kalibrierter Strafterm (EUR/kWh)
    net_at_k_final: float            # erzielter Netto-Gewinn bei k_final
    history: list = field(default_factory=list)  # [(k, net), ...] alle Auswertungen
    converged: bool = False


def _net_profit_at_k(
    k, price, consumption, plugged, battery, baseline_plan,
    fcr, cost_per_kwh, temp,
) -> float:
    """Netto-Gewinn (best case) fuer einen gegebenen Strafterm k."""
    plan = run_rolling_year(price, consumption, plugged, battery,
                            wear_cost_per_kwh=k,
                            fcr_price_eur_per_kw_per_step=fcr)
    baseline_trading = float(np.sum(
        price * (baseline_plan.discharge_kwh - baseline_plan.charge_kwh)))
    incremental_trading = plan.total_profit_eur - baseline_trading
    cmp = compare_baseline_vs_v2g(
        baseline_plan.charge_kwh, baseline_plan.discharge_kwh,
        plan.charge_kwh, plan.discharge_kwh, consumption, battery, temp)
    deg = degradation_cost_eur(cmp.extra_fade_percent, battery.capacity_kwh, cost_per_kwh)
    return incremental_trading + plan.total_fcr_revenue_eur - deg


def calibrate_wear_cost(
    price_eur_per_kwh: np.ndarray,
    consumption_kwh: np.ndarray,
    plugged_in: np.ndarray,
    battery: BatteryModel,
    baseline_plan: YearPlan,
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,
    cost_per_kwh: float = config.BATTERY_COST_EUR_PER_KWH,
    k_max: float = 0.50,             # Obergrenze fuer die Suche (50 ct/kWh)
    temp_ambient_c: float = 25.0,
    verbose: bool = True,
    # Akzeptiert (und ignoriert) Alt-Parameter fuer Rueckwaertskompatibilitaet:
    **_legacy,
) -> CalibrationResult:
    """Findet per 1-D-Optimierung (Brent, bounded) das k, das Netto(k) maximiert."""
    history: list = []

    def neg_net(k: float) -> float:
        net = _net_profit_at_k(k, price_eur_per_kwh, consumption_kwh, plugged_in,
                               battery, baseline_plan, fcr_price_eur_per_kw_per_step,
                               cost_per_kwh, temp_ambient_c)
        history.append((float(k), float(net)))
        if verbose:
            print(f"    k={k*100:6.2f} ct/kWh -> Netto {net:8.1f} EUR")
        return -net

    res = minimize_scalar(neg_net, bounds=(0.0, k_max), method="bounded",
                          options={"xatol": 0.003, "maxiter": 20})

    return CalibrationResult(
        k_final=float(res.x),
        net_at_k_final=float(-res.fun),
        history=history,
        converged=bool(res.success),
    )
