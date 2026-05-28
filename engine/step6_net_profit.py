"""
step6_net_profit.py
===================

SCHRITT 6: Verschleiss in den Optimierer einbauen und den EHRLICHEN
Netto-Gewinn berechnen.

Hintergrund (aus Schritt 5):
Ohne Verschleiss-Strafe zyklt der Optimierer viel zu aggressiv -> riesige
Mehralterung -> Verlustgeschaeft. Loesung: ein linearer Strafterm pro kWh
Durchsatz im Optimierer (Schritt 4 hat dafuer jetzt den Parameter
`wear_cost_per_kwh`).

Dieses Modul bietet:

  1) degradation_cost_eur(...)
        Rechnet die vom KIT-Modell gemessene Mehralterung (% Kapazitaet) in
        Euro um (verlorene Pack-Kapazitaet * Akkukosten pro kWh).

  2) evaluate_scenario(...)
        Fuehrt fuer EINEN gewaehlten Strafterm den kompletten Ablauf aus:
          - V2G-Plan optimieren (mit Strafterm),
          - mit dem KIT-Modell gegen die Baseline bewerten,
          - Handelsgewinn, Mehralterung, Degradationskosten und Netto-Gewinn
            zurueckgeben.

So sieht man, wie sich der Strafterm auf das echte Ergebnis auswirkt - und
kann den besten Wert waehlen (der den Netto-Gewinn maximiert).

Wichtig zur Trennung:
  - Der Strafterm `wear_cost_per_kwh` STEUERT nur den Optimierer (LP-tauglich,
    linear). Er ist NICHT der echte Cashflow.
  - Die ECHTEN Degradationskosten kommen aus dem nichtlinearen KIT-Modell und
    fliessen erst hier in den Netto-Gewinn ein.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config
from .step3_battery import BatteryModel
from .step4_optimizer import YearPlan, run_rolling_year
from .step5_degradation_kit import compare_baseline_vs_v2g, fcr_worst_case_activation_kw
from .step9_fcr_pool import apply_min_lot


def degradation_cost_eur(
    extra_fade_percent: float,
    capacity_kwh: float,
    cost_per_kwh: float = config.BATTERY_COST_EUR_PER_KWH,
    eol_loss_pct: float = config.BATTERY_EOL_LOSS_PCT,
) -> float:
    """Euro-Wert der V2G-Mehralterung (End-of-Life-Modell).

    Idee: Die Batterie ist am Lebensende, wenn sie `eol_loss_pct` % ihrer
    Kapazitaet verloren hat (z.B. 20 % -> 80 % Restkapazitaet). Die GESAMTEN
    Akkukosten verteilen sich also auf nur diese eol_loss_pct % nutzbaren
    Verlust. Die V2G-Mehralterung verbraucht davon den Anteil
    extra_fade_percent / eol_loss_pct.

        Kosten = (extra_fade_percent / eol_loss_pct) * (capacity_kwh * cost_per_kwh)

    Spezialfall eol_loss_pct = 100 -> simples lineares pro-rata-Modell
    (jede verlorene kWh = anteilig Neupreis, ohne EoL-Schwelle)."""
    total_battery_cost = capacity_kwh * cost_per_kwh
    return (extra_fade_percent / eol_loss_pct) * total_battery_cost


@dataclass
class ScenarioResult:
    wear_cost_per_kwh: float          # benutzter Strafterm
    trading_profit_eur: float         # INKREMENTELLER Arbitrage-Vorteil ggue. Baseline
    fcr_revenue_eur: float            # FCR-Verfuegbarkeitserloes (Schritt 7)
    throughput_kwh: float             # geladene + entladene kWh im Jahr
    discharged_kwh: float             # ins Netz eingespeiste kWh
    # --- BEST CASE: FCR wird nicht abgerufen (kein FCR-Verschleiss) ---
    extra_fade_percent: float         # V2G-Mehralterung laut KIT-Modell
    degradation_cost_eur: float       # Euro-Wert dieser Mehralterung
    net_profit_eur: float             # Arbitrage + FCR - Degradation (best case)
    # --- WORST CASE: FCR-Leistung dauernd voll abgerufen ---
    extra_fade_percent_worst: float
    degradation_cost_worst_eur: float
    net_profit_worst_eur: float
    # --- Baseline-Fallback: kein V2G ist immer eine Option (Netto 0) ---
    net_realized_eur: float           # max(0, net_profit_eur) - die ehrliche Zahl
    fallback_used: bool               # True, wenn Nichtstun besser waere
    plan: YearPlan                    # der volle Plan (fuer Plots etc.)


def evaluate_scenario(
    price_eur_per_kwh: np.ndarray,
    consumption_kwh: np.ndarray,
    plugged_in: np.ndarray,
    battery: BatteryModel,
    wear_cost_per_kwh: float,
    baseline_charge_kwh: np.ndarray,
    baseline_discharge_kwh: np.ndarray,
    cost_per_kwh: float = config.BATTERY_COST_EUR_PER_KWH,
    temp_ambient_c: float = 25.0,
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,
    fcr_activation_hours: float = 0.25,
    pool_size: int | None = None,
) -> ScenarioResult:
    """Kompletter Ablauf fuer einen Strafterm-Wert. Die Baseline (Plan ohne
    V2G) wird von aussen uebergeben, weil sie fuer alle Szenarien gleich ist
    und nur einmal berechnet werden muss.

    fcr_price_eur_per_kw_per_step (optional, Schritt 7): schaltet die
    FCR-Vermarktung mit ein. Der FCR-Erloes fliesst in den Netto-Gewinn.

    pool_size (optional, Schritt 9): Anzahl identischer Autos im Aggregator-Pool.
    Wenn gesetzt, zaehlt der FCR-Erloes nur in Schritten, in denen der Pool die
    1-MW-Mindestlosgroesse erreicht (pool_size * fcr_kw >= 1 MW). Bei zu kleinem
    Pool faellt der FCR-Erloes weg. None = Pool als ausreichend gross angenommen.

    Hinweis: Wir nehmen FCR als akkuschonend an (kleine, symmetrische, im
    Mittel energieneutrale Auslenkungen) und rechnen ihm KEINE zusaetzliche
    Degradation an (best case) bzw. den Worst-Case-Abruf separat.
    """
    # 1) V2G(+FCR)-Plan mit Strafterm optimieren
    v2g = run_rolling_year(
        price_eur_per_kwh, consumption_kwh, plugged_in, battery,
        wear_cost_per_kwh=wear_cost_per_kwh,
        fcr_price_eur_per_kw_per_step=fcr_price_eur_per_kw_per_step,
        fcr_activation_hours=fcr_activation_hours,
    )
    # INKREMENTELLER Arbitrage-Vorteil: Die Stromkosten fuers FAHREN fallen in
    # beiden Welten an (Baseline und V2G) und muessen sich rausheben. Wir
    # vergleichen daher den Handels-Cashflow GEGEN die Baseline, nicht absolut.
    baseline_trading = float(np.sum(
        price_eur_per_kwh * (baseline_discharge_kwh - baseline_charge_kwh)))
    incremental_trading = v2g.total_profit_eur - baseline_trading

    # FCR-Erloes: 1-MW-Mindestlosgroesse beruecksichtigen (Schritt 9).
    fcr_revenue = v2g.total_fcr_revenue_eur
    if pool_size is not None and v2g.fcr_kw is not None and fcr_price_eur_per_kw_per_step is not None:
        pool_res = apply_min_lot(v2g.fcr_kw, pool_size)
        fcr_revenue = float(np.sum(fcr_price_eur_per_kw_per_step
                                   * pool_res.fcr_kw_marketable))

    revenue = incremental_trading + fcr_revenue

    # 2a) BEST CASE: FCR wird nicht abgerufen -> nur Arbitrage-Zyklen altern
    cmp_best = compare_baseline_vs_v2g(
        baseline_charge_kwh, baseline_discharge_kwh,
        v2g.charge_kwh, v2g.discharge_kwh,
        consumption_kwh, battery, temp_ambient_c,
    )
    deg_best = degradation_cost_eur(cmp_best.extra_fade_percent,
                                    battery.capacity_kwh, cost_per_kwh)
    net_best = revenue - deg_best

    # 2b) WORST CASE: FCR-Leistung wird dauernd voll abgerufen -> Extra-Verschleiss
    if v2g.fcr_kw is not None and v2g.fcr_kw.sum() > 0:
        worst_activation = fcr_worst_case_activation_kw(v2g.fcr_kw)
        cmp_worst = compare_baseline_vs_v2g(
            baseline_charge_kwh, baseline_discharge_kwh,
            v2g.charge_kwh, v2g.discharge_kwh,
            consumption_kwh, battery, temp_ambient_c,
            fcr_activation_kw=worst_activation,
        )
        deg_worst = degradation_cost_eur(cmp_worst.extra_fade_percent,
                                         battery.capacity_kwh, cost_per_kwh)
        fade_worst = cmp_worst.extra_fade_percent
    else:
        # Kein FCR -> worst == best
        deg_worst = deg_best
        fade_worst = cmp_best.extra_fade_percent
    net_worst = revenue - deg_worst

    # 3) Baseline-Fallback: kein V2G zu machen ist immer moeglich (Netto 0).
    #    Wir berichten daher max(0, net_best) als ehrlich realisierbaren Wert.
    net_realized = max(0.0, net_best)
    fallback_used = net_best < 0

    return ScenarioResult(
        wear_cost_per_kwh=wear_cost_per_kwh,
        trading_profit_eur=incremental_trading,
        fcr_revenue_eur=fcr_revenue,
        throughput_kwh=float(v2g.charge_kwh.sum() + v2g.discharge_kwh.sum()),
        discharged_kwh=float(v2g.discharge_kwh.sum()),
        extra_fade_percent=cmp_best.extra_fade_percent,
        degradation_cost_eur=deg_best,
        net_profit_eur=net_best,
        extra_fade_percent_worst=fade_worst,
        degradation_cost_worst_eur=deg_worst,
        net_profit_worst_eur=net_worst,
        net_realized_eur=net_realized,
        fallback_used=fallback_used,
        plan=v2g,
    )
