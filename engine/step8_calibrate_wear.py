"""
step8_calibrate_wear.py
=======================

SCHRITT 8: Den Verschleiss-Strafterm k selbstkonsistent kalibrieren
(Fixpunkt-Iteration).

Problem (aus der Diskussion): In Schritt 6 haben wir k von Hand auf 2 ct/kWh
gesetzt. Ist k zu niedrig, tradet der Optimierer zu viel; ist k zu hoch, zu
wenig. Wir wollen k so, dass es die TATSAECHLICHEN Verschleisskosten pro kWh
trifft, die das KIT-Modell im Betriebspunkt misst.

Fixpunkt-Idee:
  1) optimiere V2G-Plan mit aktuellem k
  2) miss mit dem KIT-Modell die echten V2G-Mehralterungskosten (EUR)
  3) teile durch den ZUSAETZLICHEN Durchsatz (V2G ueber Baseline hinaus)
     -> tatsaechliche Kosten pro kWh
  4) setze k = diese Kosten (mit etwas Daempfung fuer Stabilitaet)
  5) wiederhole, bis sich k kaum noch aendert

Hinweis: Das trifft die DURCHSCHNITTLICHEN Mehrkosten pro kWh. Weil die echte
Alterung konvex ist (mehr Zyklen -> ueberproportional mehr Verschleiss), liegen
die GRENZkosten etwas hoeher. Der Baseline-Fallback aus Schritt 6 faengt den
Rest ab (Netto kann nie unter 0 fallen). Fuer exakte Grenzkosten muesste man
eine finite Differenz zweier Durchsatz-Niveaus bilden - hier bewusst einfach.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config
from .step3_battery import BatteryModel
from .step4_optimizer import run_rolling_year, YearPlan
from .step5_degradation_kit import compare_baseline_vs_v2g
from .step6_net_profit import degradation_cost_eur


@dataclass
class CalibrationResult:
    k_final: float                   # kalibrierter Strafterm (EUR/kWh)
    history: list[tuple]             # [(k_in, extra_throughput, k_out), ...]
    converged: bool


def calibrate_wear_cost(
    price_eur_per_kwh: np.ndarray,
    consumption_kwh: np.ndarray,
    plugged_in: np.ndarray,
    battery: BatteryModel,
    baseline_plan: YearPlan,
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,
    cost_per_kwh: float = config.BATTERY_COST_EUR_PER_KWH,
    k_start: float = 0.02,
    max_iter: int = 6,
    tol: float = 0.001,              # Konvergenz, wenn |k_neu - k| < 1 ct/10
    damping: float = 0.5,            # 0..1, daempft die k-Anpassung
    temp_ambient_c: float = 25.0,
    verbose: bool = True,
) -> CalibrationResult:
    """Findet per Fixpunkt-Iteration den selbstkonsistenten Strafterm k."""
    baseline_throughput = float(baseline_plan.charge_kwh.sum()
                                + baseline_plan.discharge_kwh.sum())

    k = k_start
    history = []
    converged = False

    for it in range(max_iter):
        # 1) Plan mit aktuellem k
        plan = run_rolling_year(
            price_eur_per_kwh, consumption_kwh, plugged_in, battery,
            wear_cost_per_kwh=k,
            fcr_price_eur_per_kw_per_step=fcr_price_eur_per_kw_per_step,
        )
        throughput = float(plan.charge_kwh.sum() + plan.discharge_kwh.sum())
        extra_throughput = throughput - baseline_throughput

        if extra_throughput <= 1e-6:
            # Der Optimierer tradet nicht mehr ueber die Baseline hinaus.
            if verbose:
                print(f"    Iter {it}: k={k*100:.2f} ct -> kein Mehr-Durchsatz, stop.")
            history.append((k, 0.0, k))
            converged = True
            break

        # 2) echte Mehralterungskosten messen
        cmp = compare_baseline_vs_v2g(
            baseline_plan.charge_kwh, baseline_plan.discharge_kwh,
            plan.charge_kwh, plan.discharge_kwh,
            consumption_kwh, battery, temp_ambient_c,
        )
        deg_cost = degradation_cost_eur(cmp.extra_fade_percent,
                                        battery.capacity_kwh, cost_per_kwh)

        # 3) tatsaechliche Kosten pro zusaetzlicher kWh Durchsatz
        k_measured = deg_cost / extra_throughput

        if verbose:
            print(f"    Iter {it}: k={k*100:.2f} ct -> Mehr-Durchsatz "
                  f"{extra_throughput:.0f} kWh, Degr {deg_cost:.0f} EUR "
                  f"-> gemessen {k_measured*100:.2f} ct/kWh")

        history.append((k, extra_throughput, k_measured))

        # 4) k aktualisieren (gedaempft)
        k_new = (1 - damping) * k + damping * k_measured
        if abs(k_new - k) < tol:
            k = k_new
            converged = True
            break
        k = k_new

    return CalibrationResult(k_final=k, history=history, converged=converged)
