"""
step4_optimizer.py
==================

SCHRITT 4: Der Optimierer (das Herzstueck).

Er entscheidet fuer jeden 15-Min-Schritt, wie viel geladen/entladen wird,
um den Gewinn zu maximieren - unter Einhaltung aller Akku-Grenzen und mit
der Garantie, dass jede Fahrt fahrbar bleibt.

Es gibt zwei Ebenen:

  1) optimize_window(...)
        Loest EIN Optimierungsfenster (z.B. 2 Tage) als lineares Programm.
        Bekommt: Preise, Fahrverbrauch, Stecker-Status, Akku, Start-SoC.
        Liefert: optimaler Lade-/Entlade-Plan + SoC-Verlauf fuer das Fenster.

  2) run_rolling_year(...)
        Die "rollierende" Planung uebers ganze Jahr (Receding Horizon / MPC):
        - Plane ein Fenster von LOOKAHEAD Tagen ab dem aktuellen Tag.
        - Uebernimm nur die Entscheidungen fuer die ersten COMMIT Tage.
        - Schiebe das Fenster weiter, plane neu - mit dem SoC, der sich aus
          den uebernommenen Entscheidungen ergeben hat.
        So blickt der Optimierer NIE weiter als LOOKAHEAD Tage voraus
        (kein "Jahres-Hellsehen"), genau wie im echten Day-Ahead-Markt.

Warum LOOKAHEAD groesser als COMMIT sein muss:
  Wuerde der Optimierer nur genau den Tag sehen, den er umsetzt, wuerde er den
  Akku abends komplett leerverkaufen (danach ja "egal"). Indem er einen Tag
  WEITER schaut (aber nur den ersten umsetzt), sieht er die Fahrt am naechsten
  Morgen und haelt automatisch genug Energie zurueck.

Das lineare Programm (pro Fenster, Schritte t = 0..N-1)
------------------------------------------------------
Variablen:
    charge[t]    >= 0   Energie aus dem Netz   (kWh)   - nur wenn angesteckt
    discharge[t] >= 0   Energie ins Netz       (kWh)   - nur wenn angesteckt
    soc[t]              Ladestand              (kWh)

Nebenbedingungen:
    soc[0]   = start_soc
    soc[t+1] = soc[t] + eff_c*charge[t] - (1/eff_d)*discharge[t] - verbrauch[t]
    soc_min <= soc[t] <= soc_max         (fuer ALLE t  -> Fahrt-Garantie!)
    charge[t], discharge[t] <= max. Energie pro Schritt
    charge[t] = discharge[t] = 0  wenn nicht angesteckt

Zielfunktion (maximieren):
    Summe ueber t von   preis[t] * (discharge[t] - charge[t])
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pulp

from .config import (
    BATTERY_START_SOC_FRAC,
    STEP_HOURS,
    STEPS_PER_DAY,
    TOTAL_STEPS,
)
from .step3_battery import BatteryModel, simulate_soc


# ---------------------------------------------------------------------------
# Ebene 1: ein einzelnes Optimierungsfenster loesen
# ---------------------------------------------------------------------------

@dataclass
class WindowResult:
    charge_kwh: np.ndarray       # (N,)
    discharge_kwh: np.ndarray    # (N,)
    soc_kwh: np.ndarray          # (N+1,)
    profit_eur: float            # Handelsgewinn (Arbitrage) ueber das Fenster
    feasible: bool
    fcr_kw: np.ndarray | None = None       # (N,) angebotene FCR-Leistung pro Schritt
    fcr_revenue_eur: float = 0.0           # FCR-Erloes ueber das Fenster


def optimize_window(
    price_eur_per_kwh: np.ndarray,   # (N,) Preis pro Schritt in EUR/kWh
    consumption_kwh: np.ndarray,     # (N,) Fahrverbrauch pro Schritt
    plugged_in: np.ndarray,          # (N,) bool: angesteckt?
    battery: BatteryModel,
    start_soc_kwh: float,
    end_soc_min_kwh: float | None = None,   # Mindest-SoC am Fensterende (optional)
    allow_discharge: bool = True,    # False = Baseline (nur laden, kein V2G-Entladen)
    wear_cost_per_kwh: float | np.ndarray = 0.0,  # Verschleiss-Strafe pro kWh.
                                     # Skalar (konstantes k) ODER Array der Laenge N
                                     # (zeitvariables k[t], z.B. aus k(SoC), Schritt 10)
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,  # FCR-Preis (EUR/kW/Schritt)
    fcr_activation_hours: float = 0.25,  # vorzuhaltende Abruf-Dauer (15 min)
) -> WindowResult:
    """Loest ein Fenster als lineares Programm und gibt den optimalen Plan.

    allow_discharge=False erzwingt entladen[t]=0 fuer alle t. Damit erhaelt man
    die "Baseline": das Auto laedt nur fuer seine Fahrten und speist nichts ins
    Netz zurueck (kein V2G). Das brauchen wir in Schritt 5 als Vergleichsbasis.

    wear_cost_per_kwh > 0 fuegt einen linearen Verschleiss-Strafterm hinzu:
    jede geladene und entladene kWh kostet diesen Betrag. Damit haelt sich der
    Optimierer zurueck und macht nur noch die lohnenden grossen Preisspruenge
    (Schritt 6).

    fcr_price_eur_per_kw_per_step (optional, Schritt 7): wenn gesetzt, kann das
    Auto pro Schritt FCR-Leistung anbieten und dafuer eine Verfuegbarkeitszahlung
    verdienen. Dafuer muss es symmetrischen SoC-Puffer vorhalten (Abruf in beide
    Richtungen fuer `fcr_activation_hours`), und die Lader-Leistung wird zwischen
    Arbitrage und FCR aufgeteilt.
    """
    N = len(price_eur_per_kwh)
    soc_min = battery.soc_min_kwh
    soc_max = battery.soc_max_kwh
    max_step = battery.max_energy_per_step_kwh
    use_fcr = fcr_price_eur_per_kw_per_step is not None
    # Verschleiss-Strafe: Skalar -> konstantes Array; sonst pro-Schritt-Array
    if np.isscalar(wear_cost_per_kwh):
        wear_arr = np.full(N, float(wear_cost_per_kwh))
    else:
        wear_arr = np.asarray(wear_cost_per_kwh, dtype=float)

    prob = pulp.LpProblem("v2g_window", pulp.LpMaximize)

    # --- Variablen ---
    charge = [pulp.LpVariable(f"c{t}", lowBound=0, upBound=max_step) for t in range(N)]
    discharge = [pulp.LpVariable(f"d{t}", lowBound=0, upBound=max_step) for t in range(N)]
    soc = [pulp.LpVariable(f"s{t}", lowBound=soc_min, upBound=soc_max) for t in range(N + 1)]
    # FCR-Leistung pro Schritt (kW), nur wenn FCR aktiv
    fcr = ([pulp.LpVariable(f"f{t}", lowBound=0, upBound=battery.power_kw) for t in range(N)]
           if use_fcr else None)

    # --- Nebenbedingungen ---
    prob += soc[0] == start_soc_kwh
    for t in range(N):
        # Ohne Stecker: weder laden noch entladen noch FCR
        if not plugged_in[t]:
            prob += charge[t] == 0
            prob += discharge[t] == 0
            if use_fcr:
                prob += fcr[t] == 0
        # Baseline-Modus: gar kein Entladen erlaubt
        if not allow_discharge:
            prob += discharge[t] == 0
        # SoC-Fortschreibung (Energiebilanz aus Schritt 3)
        prob += soc[t + 1] == (
            soc[t]
            + battery.eff_charge * charge[t]
            - (1.0 / battery.eff_discharge) * discharge[t]
            - consumption_kwh[t]
        )
        # soc_min <= soc[t] <= soc_max gilt schon ueber die Variablen-Grenzen;
        # damit ist die Fahrt-Garantie automatisch erfuellt (SoC kann nie unter
        # das Minimum fallen, auch nicht waehrend einer Fahrt).

        if use_fcr:
            # 1) Leistung teilen: Arbitrage-Leistung + FCR-Leistung <= Lader-Leistung
            #    (in Energie-Einheiten pro Schritt: *STEP_HOURS)
            prob += charge[t] + discharge[t] + fcr[t] * STEP_HOURS <= max_step
            # 2) Symmetrischer SoC-Puffer: selbst wenn der FCR-Abruf die volle
            #    Leistung fuer fcr_activation_hours zieht, muss der SoC im
            #    erlaubten Band bleiben (Anfang UND Ende des Schritts).
            #    fcr_buffer (kWh) = fcr_kw * Abrufdauer
            buf = fcr[t] * fcr_activation_hours
            prob += soc[t] - buf >= soc_min       # genug zum Abgeben (Fahrt-Garantie!)
            prob += soc[t] + buf <= soc_max       # genug Platz zum Aufnehmen
            prob += soc[t + 1] - buf >= soc_min
            prob += soc[t + 1] + buf <= soc_max

    if end_soc_min_kwh is not None:
        prob += soc[N] >= end_soc_min_kwh

    # --- Zielfunktion: Arbitrage-Gewinn + FCR-Erloes - Verschleiss-Strafe ---
    erloes = pulp.lpSum(
        price_eur_per_kwh[t] * (discharge[t] - charge[t]) for t in range(N)
    )
    verschleiss = pulp.lpSum(
        wear_arr[t] * (charge[t] + discharge[t]) for t in range(N)
    )
    fcr_erloes = (pulp.lpSum(fcr_price_eur_per_kw_per_step[t] * fcr[t] for t in range(N))
                  if use_fcr else 0)
    prob += erloes - verschleiss + fcr_erloes

    # --- Loesen (CBC, leise) ---
    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    feasible = pulp.LpStatus[status] == "Optimal"

    if not feasible:
        # Notfall: nichts handeln, nur fahren (Akku-SoC sinkt durch Verbrauch).
        c = np.zeros(N)
        d = np.zeros(N)
        s = np.empty(N + 1)
        s[0] = start_soc_kwh
        for t in range(N):
            s[t + 1] = s[t] - consumption_kwh[t]
        return WindowResult(c, d, s, profit_eur=0.0, feasible=False,
                            fcr_kw=(np.zeros(N) if use_fcr else None))

    c = np.array([pulp.value(x) or 0.0 for x in charge])
    d = np.array([pulp.value(x) or 0.0 for x in discharge])
    s = np.array([pulp.value(x) or 0.0 for x in soc])
    profit = float(np.sum(price_eur_per_kwh * (d - c)))

    f = None
    fcr_rev = 0.0
    if use_fcr:
        f = np.array([pulp.value(x) or 0.0 for x in fcr])
        fcr_rev = float(np.sum(fcr_price_eur_per_kw_per_step * f))

    return WindowResult(c, d, s, profit_eur=profit, feasible=True,
                        fcr_kw=f, fcr_revenue_eur=fcr_rev)


# ---------------------------------------------------------------------------
# Ebene 2: rollierende Planung uebers ganze Jahr
# ---------------------------------------------------------------------------

@dataclass
class YearPlan:
    charge_kwh: np.ndarray       # (TOTAL_STEPS,)
    discharge_kwh: np.ndarray    # (TOTAL_STEPS,)
    soc_kwh: np.ndarray          # (TOTAL_STEPS+1,)
    profit_per_step_eur: np.ndarray   # (TOTAL_STEPS,) Arbitrage-Gewinn je Schritt
    total_profit_eur: float           # Arbitrage-Gewinn gesamt
    infeasible_days: int
    fcr_kw: np.ndarray | None = None  # (TOTAL_STEPS,) angebotene FCR-Leistung
    total_fcr_revenue_eur: float = 0.0  # FCR-Erloes gesamt


def run_rolling_year(
    price_eur_per_kwh: np.ndarray,   # (TOTAL_STEPS,)
    consumption_kwh: np.ndarray,     # (TOTAL_STEPS,)
    plugged_in: np.ndarray,          # (TOTAL_STEPS,)
    battery: BatteryModel,
    start_soc_kwh: float | None = None,
    lookahead_days: int = 2,         # wie weit der Optimierer schaut
    commit_days: int = 1,            # wie viele Tage er davon umsetzt
    allow_discharge: bool = True,    # False = Baseline (nur laden, kein V2G)
    wear_cost_per_kwh: float | np.ndarray = 0.0,  # Skalar ODER Array (zeitvariables k[t])
    fcr_price_eur_per_kw_per_step: np.ndarray | None = None,  # FCR-Preis (Schritt 7)
    fcr_activation_hours: float = 0.25,
    progress: bool = False,
) -> YearPlan:
    """Plant rollierend (siehe Modul-Doku). Laenge der Eingabe-Arrays bestimmt
    den simulierten Zeitraum - es muss kein ganzes Jahr sein, aber ein
    Vielfaches eines Tages (96 Schritte)."""
    n_steps = len(price_eur_per_kwh)
    assert n_steps % STEPS_PER_DAY == 0, "Laenge muss ein Vielfaches eines Tages (96) sein"
    use_fcr = fcr_price_eur_per_kw_per_step is not None

    if start_soc_kwh is None:
        start_soc_kwh = BATTERY_START_SOC_FRAC * battery.capacity_kwh

    charge_year = np.zeros(n_steps)
    discharge_year = np.zeros(n_steps)
    fcr_year = np.zeros(n_steps) if use_fcr else None
    soc_year = np.zeros(n_steps + 1)
    soc_year[0] = start_soc_kwh

    commit_steps = commit_days * STEPS_PER_DAY
    look_steps = lookahead_days * STEPS_PER_DAY

    current_soc = start_soc_kwh
    infeasible_days = 0

    start = 0
    while start < n_steps:
        # Fenster = [start, window_end), aber nicht ueber das Ende hinaus
        window_end = min(start + look_steps, n_steps)
        commit_end = min(start + commit_steps, n_steps)

        # Ist dies das letzte Fenster (kein "morgen" mehr zum Vorausschauen)?
        is_last = window_end >= n_steps
        # Im letzten Fenster: Akku am Ende nicht leerraeumen -> auf Startniveau halten
        end_min = start_soc_kwh if is_last else None

        fcr_slice = (fcr_price_eur_per_kw_per_step[start:window_end]
                     if use_fcr else None)
        # Verschleiss-Strafe: zeitvariables Array aufs Fenster zuschneiden
        wear_slice = (wear_cost_per_kwh[start:window_end]
                      if not np.isscalar(wear_cost_per_kwh) else wear_cost_per_kwh)
        res = optimize_window(
            price_eur_per_kwh[start:window_end],
            consumption_kwh[start:window_end],
            plugged_in[start:window_end],
            battery,
            start_soc_kwh=current_soc,
            end_soc_min_kwh=end_min,
            allow_discharge=allow_discharge,
            wear_cost_per_kwh=wear_slice,
            fcr_price_eur_per_kw_per_step=fcr_slice,
            fcr_activation_hours=fcr_activation_hours,
        )

        # Nur die ersten (commit_end - start) Schritte uebernehmen
        n_commit = commit_end - start
        charge_year[start:commit_end] = res.charge_kwh[:n_commit]
        discharge_year[start:commit_end] = res.discharge_kwh[:n_commit]
        if use_fcr:
            fcr_year[start:commit_end] = res.fcr_kw[:n_commit]
        # SoC fortschreiben
        for k in range(n_commit):
            soc_year[start + k + 1] = res.soc_kwh[k + 1]
        current_soc = soc_year[commit_end]

        if not res.feasible:
            infeasible_days += commit_days

        if progress and (start // commit_steps) % 30 == 0:
            day = start // STEPS_PER_DAY
            print(f"    ... Tag {day:3d}/{n_steps // STEPS_PER_DAY} geplant")

        start = commit_end

    profit_per_step = price_eur_per_kwh * (discharge_year - charge_year)
    total_fcr_rev = 0.0
    if use_fcr:
        total_fcr_rev = float(np.sum(fcr_price_eur_per_kw_per_step * fcr_year))
    return YearPlan(
        charge_kwh=charge_year,
        discharge_kwh=discharge_year,
        soc_kwh=soc_year,
        profit_per_step_eur=profit_per_step,
        total_profit_eur=float(profit_per_step.sum()),
        infeasible_days=infeasible_days,
        fcr_kw=fcr_year,
        total_fcr_revenue_eur=total_fcr_rev,
    )
