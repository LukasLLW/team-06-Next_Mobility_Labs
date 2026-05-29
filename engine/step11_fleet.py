"""
step11_fleet.py
===============

SCHRITT 11: Flotten-Aggregation mit PRO-AUTO-Akkus, taeglichen Zeitreihen und
Akku-Lebensdauer.

Jedes Auto hat seine EIGENEN Akku-Parameter (Kapazitaet, Leistung, SoC-Grenzen,
Kosten/kWh, EoL-Schwelle). Jedes Auto wird einzeln optimiert und bewertet; fuer
FCR wird die Pool-Kapazitaet aus der echten Summe der angebotenen Leistungen
gebildet (1-MW-Mindestlosgroesse).

Pro Auto liefern wir TAEGLICHE Zeitreihen (ein Wert pro Tag):
  - Gewinn durch Arbitrage / FCR
  - Verlust durch Abnutzung (Arbitrage) / (FCR worst case)
  - Netto-Gewinn best / worst case
und eine Akku-Lebensdauer-Schaetzung: wie lange der Akku ohne vs. mit V2G haelt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import config
from .config import BATTERY_START_SOC_FRAC, FCR_MIN_LOT_MW, STEPS_PER_DAY
from .step3_battery import BatteryModel
from .step4_optimizer import run_rolling_year, YearPlan
from .step5_degradation_kit import (
    CELL_CAP_NOMINAL_AH, pack_plan_to_cell_power_w,
    fcr_worst_case_activation_kw, simulate_capacity_fade,
)
from .step10_soc_wear import plan_with_soc_wear


@dataclass
class CarSpec:
    """Ein Auto: Fahr-Zeitreihen + eigener Akku + Kostenparameter + k(SoC)."""
    consumption_kwh: np.ndarray
    plugged_in: np.ndarray
    battery: BatteryModel
    cost_per_kwh: float
    eol_loss_pct: float
    k_func: object              # SoC(kWh) -> Strafe (EUR/kWh)


@dataclass
class CarResult:
    # Summen ueber den Zeitraum (EUR)
    trading_eur: float
    fcr_eur: float
    degradation_arbitrage_eur: float
    degradation_fcr_worst_eur: float
    net_best_eur: float
    net_worst_eur: float
    extra_fade_percent: float          # V2G-Mehralterung (best) ueber den Zeitraum
    # Akku-Lebensdauer (Jahre, hochgerechnet)
    life_years_no_v2g: float
    life_years_v2g_best: float
    life_years_v2g_worst: float
    # TAEGLICHE Zeitreihen (je ein Wert pro Tag, EUR)
    daily: dict = field(default_factory=dict)


@dataclass
class FleetResult:
    n_cars: int
    per_car: list[CarResult]
    total_net_best_eur: float
    total_net_worst_eur: float
    total_trading_eur: float
    total_fcr_eur: float
    total_degradation_arbitrage_eur: float
    total_degradation_fcr_worst_eur: float
    avg_net_best_per_car_eur: float
    pool_marketable_fraction: float
    peak_pool_mw: float
    daily_fleet: dict = field(default_factory=dict)   # ueber alle Autos summiert


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _daily_sum(per_step: np.ndarray) -> np.ndarray:
    """Summiert ein Pro-Schritt-Array tageweise (96 Schritte/Tag)."""
    n_days = len(per_step) // STEPS_PER_DAY
    return per_step[:n_days * STEPS_PER_DAY].reshape(n_days, STEPS_PER_DAY).sum(axis=1)


def _daily_fade_pct(aging) -> np.ndarray:
    """Taeglicher Kapazitaetsverlust in % der Nennkapazitaet (ein Wert pro Tag)."""
    cap_series = np.concatenate([[aging.cap_initial_ah], aging.cap_per_day_ah])
    daily_loss_ah = -np.diff(cap_series)          # Verlust je Tag
    return daily_loss_ah / CELL_CAP_NOMINAL_AH * 100.0


def _years_to_eol(total_fade_pct: float, n_days: int, eol_loss_pct: float) -> float:
    """Lebensdauer-Schaetzung: linear hochgerechnet auf die EoL-Schwelle."""
    if total_fade_pct <= 0:
        return float("inf")
    fade_per_year = total_fade_pct * (365.0 / n_days)
    return eol_loss_pct / fade_per_year


# ---------------------------------------------------------------------------
# Detaillierte Bewertung eines Autos
# ---------------------------------------------------------------------------

def evaluate_car_detailed(
    spec: CarSpec,
    plan: YearPlan,
    baseline: YearPlan,
    price_eur_per_kwh: np.ndarray,
    fcr_price_eur_per_kw_per_step: np.ndarray | None,
    marketable_mask: np.ndarray | None,
    temp_ambient_c: float = 25.0,
) -> CarResult:
    bat = spec.battery
    cost = spec.cost_per_kwh
    eol = spec.eol_loss_pct
    n_steps = len(spec.consumption_kwh)
    n_days = n_steps // STEPS_PER_DAY

    # --- 3 KIT-Laeufe: Baseline, V2G best, V2G worst (FCR-Vollabruf) ---
    cell_base = pack_plan_to_cell_power_w(
        baseline.charge_kwh, baseline.discharge_kwh, spec.consumption_kwh, bat.capacity_kwh)
    cell_best = pack_plan_to_cell_power_w(
        plan.charge_kwh, plan.discharge_kwh, spec.consumption_kwh, bat.capacity_kwh)
    fade_base = simulate_capacity_fade(cell_base, BATTERY_START_SOC_FRAC, temp_ambient_c)
    fade_best = simulate_capacity_fade(cell_best, BATTERY_START_SOC_FRAC, temp_ambient_c)

    if plan.fcr_kw is not None and plan.fcr_kw.sum() > 0:
        worst_act = fcr_worst_case_activation_kw(plan.fcr_kw)
        cell_worst = pack_plan_to_cell_power_w(
            plan.charge_kwh, plan.discharge_kwh, spec.consumption_kwh, bat.capacity_kwh,
            extra_activation_kw=worst_act)
        fade_worst = simulate_capacity_fade(cell_worst, BATTERY_START_SOC_FRAC, temp_ambient_c)
    else:
        fade_worst = fade_best

    # --- taegliche Fade-Differenzen -> taegliche Degradationskosten (EUR) ---
    d_base = _daily_fade_pct(fade_base)
    d_best = _daily_fade_pct(fade_best)
    d_worst = _daily_fade_pct(fade_worst)
    eur_per_pct = bat.capacity_kwh * cost / eol            # EUR je % Mehralterung
    daily_deg_arb = (d_best - d_base) * eur_per_pct        # Verschleiss durch Arbitrage
    daily_deg_fcr = (d_worst - d_best) * eur_per_pct       # zusaetzlich durch FCR (worst)

    # --- taegliche Erloese ---
    # Arbitrage inkrementell ggue. Baseline (Fahrstrom hebt sich raus)
    v2g_trade_step = price_eur_per_kwh * (plan.discharge_kwh - plan.charge_kwh)
    base_trade_step = price_eur_per_kwh * (baseline.discharge_kwh - baseline.charge_kwh)
    daily_arb = _daily_sum(v2g_trade_step) - _daily_sum(base_trade_step)

    if plan.fcr_kw is not None and fcr_price_eur_per_kw_per_step is not None:
        mask = marketable_mask if marketable_mask is not None else np.ones(n_steps, bool)
        fcr_step = fcr_price_eur_per_kw_per_step * plan.fcr_kw * mask
        daily_fcr = _daily_sum(fcr_step)
    else:
        daily_fcr = np.zeros(n_days)

    daily_net_best = daily_arb + daily_fcr - daily_deg_arb
    daily_net_worst = daily_arb + daily_fcr - daily_deg_arb - daily_deg_fcr

    # --- Akku-Lebensdauer ---
    life_no_v2g = _years_to_eol(fade_base.fade_percent, n_days, eol)
    life_best = _years_to_eol(fade_best.fade_percent, n_days, eol)
    life_worst = _years_to_eol(fade_worst.fade_percent, n_days, eol)

    return CarResult(
        trading_eur=float(daily_arb.sum()),
        fcr_eur=float(daily_fcr.sum()),
        degradation_arbitrage_eur=float(daily_deg_arb.sum()),
        degradation_fcr_worst_eur=float(daily_deg_fcr.sum()),
        net_best_eur=float(daily_net_best.sum()),
        net_worst_eur=float(daily_net_worst.sum()),
        extra_fade_percent=float(fade_best.fade_percent - fade_base.fade_percent),
        life_years_no_v2g=life_no_v2g,
        life_years_v2g_best=life_best,
        life_years_v2g_worst=life_worst,
        daily=dict(
            arbitrage_profit_eur=daily_arb,
            fcr_profit_eur=daily_fcr,
            degradation_arbitrage_eur=daily_deg_arb,
            degradation_fcr_worst_eur=daily_deg_fcr,
            net_best_eur=daily_net_best,
            net_worst_eur=daily_net_worst,
        ),
    )


# ---------------------------------------------------------------------------
# Flotte
# ---------------------------------------------------------------------------

def simulate_fleet(
    car_specs: list[CarSpec],
    price_eur_per_kwh: np.ndarray,
    fcr_price_eur_per_kw_per_step: np.ndarray | None,
    assumed_pool_cars: int | None = None,
    temp_ambient_c: float = 25.0,
) -> FleetResult:
    """Simuliert eine Flotte mit pro-Auto-Akkus und aggregiert die Ergebnisse."""
    # --- pro Auto optimieren ---
    plans, baselines = [], []
    for spec in car_specs:
        base = run_rolling_year(price_eur_per_kwh, spec.consumption_kwh, spec.plugged_in,
                                spec.battery, allow_discharge=False)
        plan, _ = plan_with_soc_wear(price_eur_per_kwh, spec.consumption_kwh,
                                     spec.plugged_in, spec.battery, spec.k_func,
                                     fcr_price_eur_per_kw_per_step=fcr_price_eur_per_kw_per_step)
        plans.append(plan)
        baselines.append(base)

    # --- Pool-FCR: echte Summe der angebotenen Leistungen je Schritt ---
    use_fcr = fcr_price_eur_per_kw_per_step is not None and plans[0].fcr_kw is not None
    marketable = None
    peak_pool_mw = 0.0
    marketable_frac = 0.0
    if use_fcr:
        pool_fcr_kw = np.sum([p.fcr_kw for p in plans], axis=0)
        scale = (assumed_pool_cars / len(plans)) if assumed_pool_cars else 1.0
        pool_check = pool_fcr_kw * scale
        marketable = (pool_check / 1000.0) >= FCR_MIN_LOT_MW
        peak_pool_mw = float(pool_check.max() / 1000.0)
        total_e = float(np.sum([p.fcr_kw for p in plans]))
        mk_e = float(np.sum([p.fcr_kw[marketable].sum() for p in plans]))
        marketable_frac = mk_e / total_e if total_e > 0 else 0.0

    # --- pro Auto detailliert bewerten ---
    per_car = [
        evaluate_car_detailed(spec, plan, base, price_eur_per_kwh,
                              fcr_price_eur_per_kw_per_step, marketable, temp_ambient_c)
        for spec, plan, base in zip(car_specs, plans, baselines)
    ]

    # --- Flotten-Aggregation (Summen + taegliche Summen) ---
    keys = ["arbitrage_profit_eur", "fcr_profit_eur", "degradation_arbitrage_eur",
            "degradation_fcr_worst_eur", "net_best_eur", "net_worst_eur"]
    daily_fleet = {k: np.sum([c.daily[k] for c in per_car], axis=0) for k in keys}

    total_net_best = sum(c.net_best_eur for c in per_car)
    return FleetResult(
        n_cars=len(per_car), per_car=per_car,
        total_net_best_eur=total_net_best,
        total_net_worst_eur=sum(c.net_worst_eur for c in per_car),
        total_trading_eur=sum(c.trading_eur for c in per_car),
        total_fcr_eur=sum(c.fcr_eur for c in per_car),
        total_degradation_arbitrage_eur=sum(c.degradation_arbitrage_eur for c in per_car),
        total_degradation_fcr_worst_eur=sum(c.degradation_fcr_worst_eur for c in per_car),
        avg_net_best_per_car_eur=total_net_best / len(per_car),
        pool_marketable_fraction=marketable_frac,
        peak_pool_mw=peak_pool_mw,
        daily_fleet=daily_fleet,
    )
