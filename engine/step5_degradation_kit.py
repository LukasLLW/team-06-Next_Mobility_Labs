"""
step5_degradation_kit.py
========================

SCHRITT 5: Echte Batterie-Alterung mit dem KIT-Modell (Variante B).

Hier kommt das KIT "bat-age-model" zum Einsatz - ein physikalisches
Zell-Alterungsmodell aus echten Labormessungen (Dissertation M. Luh, 2024,
NMC/C-SiO-Zelle, DOI 10.35097/1947).

Was dieses Modul tut
--------------------
1) Es uebersetzt unseren Pack-Plan (kWh pro 15-Min-Schritt, aus Schritt 4)
   in ein Leistungsprofil auf ZELLEBENE (Watt pro Zelle), das das KIT-Modell
   versteht.
2) Es laesst das KIT-Modell TAGEWEISE ueber das Jahr laufen und verfolgt die
   verbleibende Zellkapazitaet (capacity fade).
3) Es vergleicht zwei Faelle und bildet die Differenz:
       Baseline : Auto faehrt + laedt nur fuer die Fahrten (kein V2G)
       V2G      : Auto faehrt + voller Lade-/Entlade-Plan
   -> V2G-Mehralterung = Verlust(V2G) - Verlust(Baseline)

Die Bruecke Pack <-> Zelle
--------------------------
Das KIT-Modell rechnet eine EINZELNE Zelle (nominal 11 Wh, 3 Ah).
Unser Pack hat z.B. 75 kWh. Anzahl Zellen = 75 kWh / 11 Wh = ca. 6818.
Leistung pro Zelle = Pack-Leistung / Anzahl Zellen.
(Das entspricht genau dem Vorgehen im KIT-Code, der mit einem festen
 96s60p-Pack rechnet.)

Vorzeichen: im KIT-Modell ist Leistung POSITIV = laden, NEGATIV = entladen.
Unsere Netto-Leistung in den Akku pro Schritt:
    netto_kWh[t] = laden[t] - entladen[t] - fahren[t]
    Pack-Leistung[kW] = netto_kWh[t] / 0.25 h
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import N_DAYS, STEP_HOURS, STEP_MINUTES, STEPS_PER_DAY, TOTAL_STEPS
from .step3_battery import BatteryModel

# --- KIT-Modell importierbar machen ----------------------------------------
_BAT_DIR = Path(__file__).resolve().parents[1] / "bat-age-model"
if str(_BAT_DIR) not in sys.path:
    sys.path.insert(0, str(_BAT_DIR))

import bat_model_v01_fast as kit   # noqa: E402  (Import nach sys.path-Anpassung)

# Nennwerte der KIT-Zelle
CELL_E_NOMINAL_WH = kit.E_NOMINAL      # 11 Wh
CELL_CAP_NOMINAL_AH = kit.CAP_NOMINAL  # 3 Ah

# Zeitschritt in Sekunden fuer das KIT-Modell (passt zu unserer Zeitleiste)
DT_SECONDS = STEP_MINUTES * 60         # 900 s = 15 min


def n_cells(capacity_kwh: float) -> float:
    """Anzahl Zellen, die ein Pack dieser Kapazitaet ergeben."""
    return capacity_kwh * 1000.0 / CELL_E_NOMINAL_WH


# ---------------------------------------------------------------------------
# Teil 1: Pack-Plan -> Zell-Leistungsprofil (Watt)
# ---------------------------------------------------------------------------

def pack_plan_to_cell_power_w(
    charge_kwh: np.ndarray,
    discharge_kwh: np.ndarray,
    consumption_kwh: np.ndarray,
    capacity_kwh: float,
    extra_activation_kw: np.ndarray | None = None,
) -> np.ndarray:
    """Rechnet unseren Pack-Plan in ein Zell-Leistungsprofil (W) um.
    Positiv = laden, negativ = entladen/fahren.

    extra_activation_kw (optional): zusaetzliche, vorzeichenbehaftete
    Pack-Leistung (kW) pro Schritt - z.B. durch FCR-Abruf. Wird der normalen
    Lade-/Entlade-Leistung ueberlagert (relevant fuer den FCR-Verschleiss)."""
    net_into_battery_kwh = charge_kwh - discharge_kwh - consumption_kwh   # pro Schritt
    pack_power_kw = net_into_battery_kwh / STEP_HOURS                      # kW
    if extra_activation_kw is not None:
        pack_power_kw = pack_power_kw + extra_activation_kw
    cell_power_w = pack_power_kw * 1000.0 / n_cells(capacity_kwh)          # W pro Zelle
    return cell_power_w


def fcr_worst_case_activation_kw(fcr_kw: np.ndarray) -> np.ndarray:
    """Worst-Case-FCR-Abruf: maximaler Durchsatz, der den Ladestand NICHT
    verschiebt. Wir koppeln je zwei aufeinanderfolgende Schritte zu einem Paar
    (laden + gleich viel entladen) mit der Amplitude min(fcr in beiden Schritten).
    So bleibt der SoC exakt neutral (kein Driften, kein Ueberlauf), aber es
    entsteht maximaler Lade-/Entlade-Durchsatz -> hoechster Verschleiss.
    Best case waere einfach 0 (kein Abruf)."""
    out = np.zeros_like(fcr_kw)
    for i in range(0, len(fcr_kw) - 1, 2):
        amp = min(fcr_kw[i], fcr_kw[i + 1])   # nur so viel, wie beide Schritte koennen
        out[i] = +amp
        out[i + 1] = -amp
    return out


# ---------------------------------------------------------------------------
# Teil 2: KIT-Modell tageweise ueber das Jahr laufen lassen
# ---------------------------------------------------------------------------

@dataclass
class AgingResult:
    cap_initial_ah: float            # Anfangskapazitaet der Zelle (Ah)
    cap_final_ah: float              # Endkapazitaet nach dem Jahr (Ah)
    cap_per_day_ah: np.ndarray       # (N_DAYS,) Kapazitaet am Ende jedes Tages
    fade_ah: float                   # Verlust in Ah
    fade_percent: float              # Verlust in % der Nennkapazitaet

    @property
    def fade_percent_of_initial(self) -> float:
        return 100.0 * self.fade_ah / self.cap_initial_ah


def simulate_capacity_fade(
    cell_power_w: np.ndarray,        # (TOTAL_STEPS,) Zell-Leistung pro Schritt
    start_soc_frac: float = 0.5,
    temp_ambient_c: float = 25.0,
) -> AgingResult:
    """Laesst das KIT-Modell tageweise laufen und verfolgt den Kapazitaetsverlust.

    Die Laenge von cell_power_w bestimmt den Zeitraum (Vielfaches eines Tages).

    temp_ambient_c: konstante Umgebungstemperatur (Annahme - wir haben keine
    fahrzeugspezifischen Temperaturdaten; 25 C ist die Referenz der NREL-Studie).
    """
    n_steps = len(cell_power_w)
    assert n_steps % STEPS_PER_DAY == 0, "Laenge muss ein Vielfaches eines Tages (96) sein"
    n_days = n_steps // STEPS_PER_DAY

    cap_aged, aging_states, temp_cell, soc = kit.init(storage_soc=start_soc_frac)
    cap_initial = cap_aged

    cap_per_day = np.empty(n_days)
    for day in range(n_days):
        s = day * STEPS_PER_DAY
        e = s + STEPS_PER_DAY
        p_day = cell_power_w[s:e]
        # Das KIT-Modell erwartet eine Serie mit Sekunden-Index ab 0
        p_series = pd.Series(p_day, index=np.arange(STEPS_PER_DAY) * DT_SECONDS)
        cap_aged, aging_states, temp_cell, soc, _t_next, _p = kit.apply_power_profile(
            0, DT_SECONDS, p_series, temp_ambient_c,
            cap_aged, aging_states, temp_cell, soc,
        )
        cap_per_day[day] = cap_aged

    fade_ah = cap_initial - cap_aged
    return AgingResult(
        cap_initial_ah=cap_initial,
        cap_final_ah=cap_aged,
        cap_per_day_ah=cap_per_day,
        fade_ah=fade_ah,
        fade_percent=100.0 * fade_ah / CELL_CAP_NOMINAL_AH,
    )


# ---------------------------------------------------------------------------
# Teil 3: V2G-Mehralterung (Differenz V2G vs Baseline)
# ---------------------------------------------------------------------------

@dataclass
class DegradationComparison:
    baseline: AgingResult            # nur Fahren + Laden
    v2g: AgingResult                 # Fahren + V2G-Plan
    extra_fade_percent: float        # zusaetzliche Alterung durch V2G (% Nennkap.)
    extra_fade_ah: float


def compare_baseline_vs_v2g(
    baseline_charge: np.ndarray, baseline_discharge: np.ndarray,
    v2g_charge: np.ndarray, v2g_discharge: np.ndarray,
    consumption_kwh: np.ndarray,
    battery: BatteryModel,
    temp_ambient_c: float = 25.0,
    fcr_activation_kw: np.ndarray | None = None,
) -> DegradationComparison:
    """Bewertet Baseline- und V2G-Plan mit dem KIT-Modell und bildet die Differenz.

    fcr_activation_kw (optional): zusaetzlicher FCR-Abruf, der dem V2G-Profil
    ueberlagert wird (z.B. Worst-Case-Abruf). None = kein FCR-Abruf (best case)."""
    # Beide Laeufe starten beim selben Lade-Anteil (aus config.py).
    from .config import BATTERY_START_SOC_FRAC
    start_frac = BATTERY_START_SOC_FRAC

    cell_base = pack_plan_to_cell_power_w(
        baseline_charge, baseline_discharge, consumption_kwh, battery.capacity_kwh)
    cell_v2g = pack_plan_to_cell_power_w(
        v2g_charge, v2g_discharge, consumption_kwh, battery.capacity_kwh,
        extra_activation_kw=fcr_activation_kw)

    res_base = simulate_capacity_fade(cell_base, start_frac, temp_ambient_c)
    res_v2g = simulate_capacity_fade(cell_v2g, start_frac, temp_ambient_c)

    extra_pct = res_v2g.fade_percent - res_base.fade_percent
    extra_ah = res_v2g.fade_ah - res_base.fade_ah
    return DegradationComparison(
        baseline=res_base, v2g=res_v2g,
        extra_fade_percent=extra_pct, extra_fade_ah=extra_ah,
    )
