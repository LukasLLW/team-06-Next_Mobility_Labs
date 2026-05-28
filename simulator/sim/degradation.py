"""Simplified battery degradation cost model.

Anchored on NREL/EPRI V2G Impact Benchmark Study:
    EV-only:   ~1.5%/yr capacity fade @ 30°C
    Daily V2G: +1.8%/yr extra fade at 43% daily energy turnover

We translate that into a marginal degradation cost per kWh of *throughput*
(charging or discharging) attributable to V2G activity. Driving consumption
is treated as the baseline EV-only wear and not penalized.

This is intentionally a linear, per-kWh approximation -- good enough for an
earnings simulator and consistent with how aggregators price battery wear in
the literature.
"""
from __future__ import annotations

from dataclasses import dataclass

# NREL/EPRI benchmark: daily V2G at 43% energy turnover -> 1.8% extra/yr fade
EXTRA_FADE_PCT_PER_YEAR = 1.8 / 100
DAILY_TURNOVER_FRACTION = 0.43


@dataclass
class DegradationModel:
    capacity_kwh: float            # nameplate capacity
    battery_cost_eur: float        # CAPEX of the pack (or replacement cost)
    extra_fade_pct: float = EXTRA_FADE_PCT_PER_YEAR
    daily_turnover_frac: float = DAILY_TURNOVER_FRACTION

    def cost_per_throughput_kwh(self) -> float:
        """€/kWh of charge-or-discharge attributable to V2G wear.

        Derivation:
          extra_capacity_lost_per_year_kwh = extra_fade_pct * capacity_kwh
          v2g_throughput_per_year_kwh      = 365 * daily_turnover_frac
                                              * capacity_kwh * 2   (charge + discharge)
          cost_per_lost_capacity_kwh       = battery_cost_eur / capacity_kwh
          cost_per_throughput_kwh
              = lost_per_year * cost_per_lost / throughput_per_year
              = (extra_fade_pct * battery_cost_eur)
                / (365 * daily_turnover_frac * 2 * capacity_kwh)
        """
        denom = 365.0 * self.daily_turnover_frac * 2.0 * self.capacity_kwh
        if denom == 0:
            return 0.0
        return (self.extra_fade_pct * self.battery_cost_eur) / denom

    def annual_capacity_loss_kwh(self, total_throughput_kwh: float) -> float:
        """Linear scaling: how much nameplate capacity (kWh) is lost in a year
        of V2G operation with the given total throughput (charge + discharge)."""
        baseline_yearly_throughput = 365.0 * self.daily_turnover_frac * self.capacity_kwh * 2.0
        if baseline_yearly_throughput == 0:
            return 0.0
        return self.extra_fade_pct * self.capacity_kwh * (
            total_throughput_kwh / baseline_yearly_throughput
        )
