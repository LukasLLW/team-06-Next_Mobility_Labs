"""
step10_soc_wear.py
==================

SCHRITT 10: Zeitvariable Verschleiss-Strafe k(SoC) - statt EINES globalen k.

Idee (aus der Diskussion):
  - Die zyklische Alterung pro kWh haengt v.a. davon ab, BEI WELCHEM SoC
    zyklisiert wird (Zyklen bei hohem/sehr niedrigem SoC schaden mehr).
  - Also: kalibriere EINMAL eine Funktion k(SoC) per KIT-Sweep ueber den
    SoC-Wertebereich. Danach bekommt jeder Zeitschritt seine eigene Strafe
    k(SoC[t]) - es gibt kein globales k mehr.

Der einzige Haken ist die Zirkularitaet (k[t] braucht SoC[t], der erst aus dem
LP kommt). Loesung: 1 Vorlauf mit konstantem k liefert eine SoC-Schaetzung,
damit wird k[t] = k(SoC_vorlauf[t]) fixiert und EINMAL final geloest. Kein
teurer Gradient, kein Sweep - nur 2 LP-Laeufe.
"""

from __future__ import annotations

import numpy as np

from . import config
from .config import STEP_HOURS, STEPS_PER_DAY
from .step3_battery import BatteryModel
from .step4_optimizer import run_rolling_year, YearPlan
from .step5_degradation_kit import n_cells, simulate_capacity_fade
from .step6_net_profit import degradation_cost_eur


# ---------------------------------------------------------------------------
# Teil 1: k(SoC) kalibrieren (einmaliger KIT-Sweep)
# ---------------------------------------------------------------------------

def calibrate_k_of_soc(
    battery: BatteryModel,
    soc_grid: np.ndarray | None = None,
    days: int = 20,
    temp_ambient_c: float = 25.0,
    cost_per_kwh: float = config.BATTERY_COST_EUR_PER_KWH,
    eol_loss_pct: float = config.BATTERY_EOL_LOSS_PCT,
) -> tuple[np.ndarray, np.ndarray]:
    """Misst die zyklische Verschleisskosten pro kWh bei verschiedenen mittleren
    SoC-Niveaus. Gibt (soc_grid, k_values in EUR/kWh) zurueck.

    Methode pro SoC-Stuetzstelle m:
      - Zyklus-Lauf: Zelle bei m, paarweise neutrales Laden/Entladen (haelt SoC),
        ueber `days` Tage -> Kapazitaetsverlust fade_cyc.
      - Ruhe-Lauf:   Zelle bei m, keine Last -> Kalenderalterung fade_rest.
      - zyklische Mehralterung = fade_cyc - fade_rest, in EUR pro kWh Durchsatz.
    """
    if soc_grid is None:
        soc_grid = np.array([0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85])

    n_steps = days * STEPS_PER_DAY
    nc = n_cells(battery.capacity_kwh)
    a_cell = battery.power_kw * 1000.0 / nc        # volle Lader-Leistung pro Zelle (W)

    # paarweise neutrales Zyklusprofil (+A, -A, +A, -A, ...) -> SoC bleibt bei m
    cyc = np.zeros(n_steps)
    cyc[0::2] = +a_cell
    cyc[1::2] = -a_cell
    rest = np.zeros(n_steps)

    # Pack-Durchsatz dieses Profils (kWh): |Zell-Leistung| * Zeit * Zellzahl
    pack_throughput_kwh = np.sum(np.abs(cyc)) * STEP_HOURS * nc / 1000.0

    k_values = []
    for m in soc_grid:
        fade_cyc = simulate_capacity_fade(cyc, start_soc_frac=float(m),
                                          temp_ambient_c=temp_ambient_c)
        fade_rest = simulate_capacity_fade(rest, start_soc_frac=float(m),
                                           temp_ambient_c=temp_ambient_c)
        extra_pct = fade_cyc.fade_percent - fade_rest.fade_percent
        cost_eur = degradation_cost_eur(extra_pct, battery.capacity_kwh, cost_per_kwh,
                                        eol_loss_pct=eol_loss_pct)
        k_values.append(max(0.0, cost_eur / pack_throughput_kwh))

    return np.asarray(soc_grid), np.asarray(k_values)


def make_k_of_soc(soc_grid: np.ndarray, k_values: np.ndarray, capacity_kwh: float):
    """Liefert eine Funktion: SoC (in kWh) -> Verschleiss-Strafe k (EUR/kWh).
    Linear interpoliert zwischen den Stuetzstellen."""
    def k_func(soc_kwh: np.ndarray) -> np.ndarray:
        frac = np.clip(np.asarray(soc_kwh) / capacity_kwh, soc_grid[0], soc_grid[-1])
        return np.interp(frac, soc_grid, k_values)
    return k_func


# ---------------------------------------------------------------------------
# Teil 2: Plan mit zeitvariabler Strafe k(SoC[t]) erstellen
# ---------------------------------------------------------------------------

def plan_with_soc_wear(
    price_eur_per_kwh: np.ndarray,
    consumption_kwh: np.ndarray,
    plugged_in: np.ndarray,
    battery: BatteryModel,
    k_func,
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,
    warmup_k: float | None = None,
    n_iter: int = 1,
) -> tuple[YearPlan, np.ndarray]:
    """Plant mit zeitvariabler Strafe k(SoC[t]).

    1) Vorlauf mit konstantem warmup_k -> SoC-Schaetzung.
    2) k[t] = k_func(SoC[t]); final loesen. (n_iter Wiederholungen moeglich.)

    Gibt (Plan, k_vektor) zurueck.
    """
    if warmup_k is None:
        # vernuenftiger Startwert: mittlere Strafe ueber den SoC-Bereich
        warmup_k = float(np.mean(k_func(np.linspace(
            battery.soc_min_kwh, battery.soc_max_kwh, 20))))

    plan = run_rolling_year(price_eur_per_kwh, consumption_kwh, plugged_in, battery,
                            wear_cost_per_kwh=warmup_k,
                            fcr_price_eur_per_kw_per_step=fcr_price_eur_per_kw_per_step)

    k_vec = None
    for _ in range(n_iter):
        soc_path = plan.soc_kwh[:-1]                 # SoC am Anfang jedes Schritts
        k_vec = k_func(soc_path)                     # zeitvariable Strafe
        plan = run_rolling_year(price_eur_per_kwh, consumption_kwh, plugged_in, battery,
                                wear_cost_per_kwh=k_vec,
                                fcr_price_eur_per_kw_per_step=fcr_price_eur_per_kw_per_step)

    return plan, k_vec
