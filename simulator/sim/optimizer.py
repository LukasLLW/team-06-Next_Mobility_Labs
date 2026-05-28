"""Daily LP optimizer: given known day-ahead prices for the next 24h and the
driving schedule, decide hourly charge / discharge to maximize profit minus
battery-wear cost, subject to SoC, power, and trip-readiness constraints.

Time resolution: 1 hour. Hours where the vehicle is driving cannot charge or
discharge to grid -- they only consume from the battery.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pulp


@dataclass
class BatterySpec:
    capacity_kwh: float            # nameplate
    power_kw: float                # max charge & discharge power (symmetric)
    eff_charge: float = 0.95       # one-way efficiency
    eff_discharge: float = 0.95
    soc_min_frac: float = 0.10     # never go below 10% to protect battery
    soc_max_frac: float = 0.95     # never above 95%
    soc_reserve_for_trip_frac: float = 0.20  # extra buffer above predicted trip energy


@dataclass
class DayResult:
    charge_kwh: np.ndarray         # (24,) energy drawn from grid per hour
    discharge_kwh: np.ndarray      # (24,) energy sold to grid per hour
    soc_kwh: np.ndarray            # (25,) SoC after each hour (incl. start)
    gross_revenue_eur: float       # sum(discharge*price - charge*price)
    wear_cost_eur: float           # degradation cost charged in the objective
    net_profit_eur: float          # gross - wear
    feasible: bool


def optimize_day(
    prices_eur_per_kwh: np.ndarray,    # (24,) hourly price in €/kWh
    consumption_kwh: np.ndarray,       # (24,) driving energy used per hour
    driving_mask: np.ndarray,          # (24,) bool, True when driving
    battery: BatterySpec,
    wear_cost_per_kwh: float,
    start_soc_kwh: float,
    end_soc_kwh_min: float | None = None,
) -> DayResult:
    """Solve one-day LP. Returns DayResult."""
    T = 24
    assert prices_eur_per_kwh.shape == (T,)

    soc_min = battery.soc_min_frac * battery.capacity_kwh
    soc_max = battery.soc_max_frac * battery.capacity_kwh

    if end_soc_kwh_min is None:
        # Default: end day at least as high as start (rolling sustainability).
        end_soc_kwh_min = start_soc_kwh

    prob = pulp.LpProblem("v2g_day", pulp.LpMaximize)

    # Variables
    charge = [pulp.LpVariable(f"c_{t}", lowBound=0, upBound=battery.power_kw) for t in range(T)]
    discharge = [pulp.LpVariable(f"d_{t}", lowBound=0, upBound=battery.power_kw) for t in range(T)]
    soc = [pulp.LpVariable(f"s_{t}", lowBound=soc_min, upBound=soc_max) for t in range(T + 1)]

    # Lock variables to 0 during driving (no grid connection assumed while moving)
    for t in range(T):
        if driving_mask[t]:
            prob += charge[t] == 0
            prob += discharge[t] == 0

    # SoC dynamics
    prob += soc[0] == start_soc_kwh
    for t in range(T):
        prob += soc[t + 1] == (
            soc[t]
            + battery.eff_charge * charge[t]
            - (1.0 / battery.eff_discharge) * discharge[t]
            - consumption_kwh[t]
        )

    # Ensure enough SoC just before each trip to complete it
    # (use a cumulative look-ahead: at start of hour t, remaining trip energy
    #  in the rest of the day must be coverable by SoC above soc_min + reserve).
    reserve = battery.soc_reserve_for_trip_frac * battery.capacity_kwh
    remaining_trip_energy = np.zeros(T + 1)
    for t in range(T - 1, -1, -1):
        remaining_trip_energy[t] = remaining_trip_energy[t + 1] + consumption_kwh[t]
    for t in range(T):
        # SoC entering hour t must cover all remaining trip energy + reserve
        # (this also implicitly handles the trip-readiness for hour t itself).
        prob += soc[t] >= soc_min + reserve + remaining_trip_energy[t]

    # Day-end SoC continuity
    prob += soc[T] >= end_soc_kwh_min

    # Objective: revenue - wear cost
    revenue = pulp.lpSum(
        prices_eur_per_kwh[t] * discharge[t] - prices_eur_per_kwh[t] * charge[t]
        for t in range(T)
    )
    wear = pulp.lpSum(wear_cost_per_kwh * (charge[t] + discharge[t]) for t in range(T))
    prob += revenue - wear

    solver = pulp.PULP_CBC_CMD(msg=False)
    status = prob.solve(solver)
    feasible = pulp.LpStatus[status] == "Optimal"

    if not feasible:
        # Infeasible (e.g. trip requires more energy than battery holds).
        return DayResult(
            charge_kwh=np.zeros(T),
            discharge_kwh=np.zeros(T),
            soc_kwh=np.full(T + 1, start_soc_kwh),
            gross_revenue_eur=0.0,
            wear_cost_eur=0.0,
            net_profit_eur=0.0,
            feasible=False,
        )

    c = np.array([pulp.value(x) or 0.0 for x in charge])
    d = np.array([pulp.value(x) or 0.0 for x in discharge])
    s = np.array([pulp.value(x) or 0.0 for x in soc])
    gross = float(np.sum(prices_eur_per_kwh * (d - c)))
    wear_eur = float(wear_cost_per_kwh * (c.sum() + d.sum()))
    return DayResult(
        charge_kwh=c,
        discharge_kwh=d,
        soc_kwh=s,
        gross_revenue_eur=gross,
        wear_cost_eur=wear_eur,
        net_profit_eur=gross - wear_eur,
        feasible=True,
    )
