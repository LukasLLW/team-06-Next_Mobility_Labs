"""Year-long V2G simulation: roll the daily LP across every day of 2025."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .degradation import DegradationModel
from .optimizer import BatterySpec, DayResult, optimize_day
from .schedule import DailyProfile, expand_to_year
from .prices import load_prices


@dataclass
class SimConfig:
    battery: BatterySpec
    daily_profile: DailyProfile
    battery_cost_eur: float
    grid_feed_in_fee_eur_per_kwh: float = 0.0   # network charge / tax on discharge
    start_soc_frac: float = 0.7


@dataclass
class SimResult:
    daily: pd.DataFrame                # index: date; cols: revenue/wear/net/throughput
    hourly: pd.DataFrame               # index: hour; cols: price/charge/discharge/soc/consumption
    summary: dict


def run_year(cfg: SimConfig, prices_df: pd.DataFrame | None = None) -> SimResult:
    if prices_df is None:
        prices_df = load_prices()

    # Convert €/MWh -> €/kWh and subtract feed-in fee on discharge by adjusting
    # via an effective discharge price (handled inside LP by tweaking prices).
    price_eur_kwh = prices_df["price_eur_mwh"].to_numpy() / 1000.0
    index = prices_df.index

    yearly = expand_to_year(cfg.daily_profile, index)
    consumption = yearly["consumption_kwh"].to_numpy()
    driving = yearly["driving"].to_numpy()

    deg = DegradationModel(
        capacity_kwh=cfg.battery.capacity_kwh,
        battery_cost_eur=cfg.battery_cost_eur,
    )
    wear_cost = deg.cost_per_throughput_kwh()

    days = sorted(set(index.date))
    n_hours = len(index)
    charge_arr = np.zeros(n_hours)
    discharge_arr = np.zeros(n_hours)
    soc_arr = np.zeros(n_hours)

    current_soc = cfg.start_soc_frac * cfg.battery.capacity_kwh
    daily_rows = []

    # Pre-index hour offsets per date for speed
    hour_idx_per_date: dict = {}
    for i, ts in enumerate(index):
        hour_idx_per_date.setdefault(ts.date(), []).append(i)

    feed_in_fee = cfg.grid_feed_in_fee_eur_per_kwh

    for day in days:
        hour_ids = hour_idx_per_date[day]
        if len(hour_ids) != 24:
            # DST day (23 or 25 hours). Skip with simple passthrough to keep
            # the LP fixed-size; consumption still applies.
            for h in hour_ids:
                current_soc -= consumption[h]
                soc_arr[h] = current_soc
            daily_rows.append({
                "date": day, "gross_revenue_eur": 0.0, "wear_cost_eur": 0.0,
                "net_profit_eur": 0.0, "throughput_kwh": 0.0, "feasible": False,
            })
            continue

        p = price_eur_kwh[hour_ids[0]:hour_ids[-1] + 1].copy()
        # Penalize discharge with feed-in fee: effective sell price = p - fee
        p_for_lp = p.copy()  # for charge it's the buy price
        # We tweak the LP by passing per-hour discharge_price separately: easier
        # to handle via a single price and subtracting fee from objective.
        # Simpler: just lower the effective price array seen by the LP for
        # discharge -- but LP uses same array for charge & discharge. So we
        # incorporate the fee into wear_cost_per_kwh on the discharge side via
        # equivalent cost: effective wear+fee for discharge = wear + fee.
        # Cleanest: subtract fee directly in objective post-hoc. We keep LP as
        # is with `p`, and subtract fee*sum(discharge) from gross at the end.

        cons = consumption[hour_ids[0]:hour_ids[-1] + 1]
        drv = driving[hour_ids[0]:hour_ids[-1] + 1]

        # End-of-day SoC: at least the start of next day's reserve+trip needs.
        # For simplicity require >= start_soc each day.
        res: DayResult = optimize_day(
            prices_eur_per_kwh=p,
            consumption_kwh=cons,
            driving_mask=drv,
            battery=cfg.battery,
            wear_cost_per_kwh=wear_cost + feed_in_fee,  # charge fee to discharge*fee equivalently below
            start_soc_kwh=current_soc,
            end_soc_kwh_min=cfg.start_soc_frac * cfg.battery.capacity_kwh,
        )

        # We over-charged wear by `fee` on charge too; correct by subtracting
        # fee*charge from the wear total (so fee only applies to discharge).
        charge_total = res.charge_kwh.sum()
        discharge_total = res.discharge_kwh.sum()
        wear_only = wear_cost * (charge_total + discharge_total)
        fee_total = feed_in_fee * discharge_total
        gross = res.gross_revenue_eur
        net = gross - wear_only - fee_total

        for k, h in enumerate(hour_ids):
            charge_arr[h] = res.charge_kwh[k]
            discharge_arr[h] = res.discharge_kwh[k]
            soc_arr[h] = res.soc_kwh[k + 1]  # SoC at end of hour
        current_soc = res.soc_kwh[-1]

        daily_rows.append({
            "date": day,
            "gross_revenue_eur": gross,
            "wear_cost_eur": wear_only,
            "feed_in_fee_eur": fee_total,
            "net_profit_eur": net,
            "throughput_kwh": charge_total + discharge_total,
            "feasible": res.feasible,
        })

    daily = pd.DataFrame(daily_rows).set_index("date")
    daily.index = pd.to_datetime(daily.index)

    hourly = pd.DataFrame({
        "price_eur_kwh": price_eur_kwh,
        "charge_kwh": charge_arr,
        "discharge_kwh": discharge_arr,
        "soc_kwh": soc_arr,
        "consumption_kwh": consumption,
        "driving": driving,
    }, index=index)

    total_throughput = daily["throughput_kwh"].sum()
    annual_capacity_loss = deg.annual_capacity_loss_kwh(total_throughput)
    summary = {
        "year_revenue_eur": float(daily["gross_revenue_eur"].sum()),
        "year_wear_eur": float(daily["wear_cost_eur"].sum()),
        "year_feed_in_fee_eur": float(daily["feed_in_fee_eur"].sum()),
        "year_net_eur": float(daily["net_profit_eur"].sum()),
        "avg_daily_net_eur": float(daily["net_profit_eur"].mean()),
        "total_throughput_kwh": float(total_throughput),
        "extra_capacity_loss_kwh": float(annual_capacity_loss),
        "extra_capacity_loss_pct": float(
            100.0 * annual_capacity_loss / cfg.battery.capacity_kwh
            if cfg.battery.capacity_kwh else 0.0
        ),
        "wear_cost_per_kwh": float(wear_cost),
        "infeasible_days": int((~daily["feasible"]).sum()),
    }
    return SimResult(daily=daily, hourly=hourly, summary=summary)
