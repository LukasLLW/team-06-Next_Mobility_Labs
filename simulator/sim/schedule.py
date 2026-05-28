"""Daily driving schedule → per-hour energy consumption."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

Intensity = Literal["slow", "fast"]


@dataclass
class Trip:
    start_h: float       # hour of day, e.g. 7.5 == 07:30
    end_h: float         # hour of day, exclusive
    intensity: Intensity = "slow"  # "slow" = city/Landstrasse, "fast" = Autobahn

    def duration_h(self) -> float:
        return (self.end_h - self.start_h) % 24


# Energy consumption assumptions
# A mid-size EV: city/eco ~15 kWh/100km @ ~50 km/h average  -> ~7.5 kWh/h
#                highway     ~22 kWh/100km @ ~110 km/h        -> ~24 kWh/h
CONSUMPTION_KWH_PER_HOUR = {"slow": 7.5, "fast": 24.0}


@dataclass
class DailyProfile:
    trips: list[Trip] = field(default_factory=list)

    def hourly_consumption(self) -> np.ndarray:
        """Return 24-element array of kWh consumed per hour of day."""
        out = np.zeros(24)
        for trip in self.trips:
            rate = CONSUMPTION_KWH_PER_HOUR[trip.intensity]
            s, e = trip.start_h, trip.end_h
            if e <= s:
                # Trip wraps past midnight -> split
                spans = [(s, 24.0), (0.0, e)]
            else:
                spans = [(s, e)]
            for a, b in spans:
                h = int(np.floor(a))
                while h < b:
                    next_boundary = min(h + 1, b)
                    overlap = next_boundary - max(a, h)
                    if overlap > 0:
                        out[h % 24] += overlap * rate
                    h += 1
        return out

    def driving_mask(self) -> np.ndarray:
        """24-element bool: True if vehicle is driving (not available to charge/discharge)."""
        cons = self.hourly_consumption()
        return cons > 0.0


def expand_to_year(daily: DailyProfile, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Tile a daily profile across the full hourly index."""
    cons24 = daily.hourly_consumption()
    drv24 = daily.driving_mask()
    hours = index.hour.to_numpy()
    return pd.DataFrame(
        {"consumption_kwh": cons24[hours], "driving": drv24[hours]},
        index=index,
    )
