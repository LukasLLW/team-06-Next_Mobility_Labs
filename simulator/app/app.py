"""Plug & Earn — V2G earnings simulator.

Streamlit UI: fleet operator enters battery specs + a typical daily driving
schedule, simulator runs a full year of 2025 day-ahead-price-driven dispatch
optimization, returns annual profit, degradation impact, and time-series
breakdowns.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the parent (`simulator/`) importable when running `streamlit run app/app.py`
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sim.optimizer import BatterySpec
from sim.prices import load_prices, price_source
from sim.schedule import DailyProfile, Trip
from sim.simulation import SimConfig, run_year


st.set_page_config(
    page_title="Plug & Earn — V2G Earnings Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Plug & Earn")
st.caption(
    "How much can a fleet earn by letting parked EVs trade on the day-ahead market? "
    "Enter your battery + typical driving schedule and find out."
)


# ---------- Inputs ----------

with st.sidebar:
    st.header("Battery")
    capacity_kwh = st.number_input("Capacity (kWh)", min_value=10.0, max_value=200.0, value=75.0, step=5.0)
    power_kw = st.number_input("Charger power (kW)", min_value=3.7, max_value=150.0, value=11.0, step=1.0,
                               help="Max bidirectional power. AC wallbox: 3.7–22, DC: 50–150.")
    battery_cost_eur = st.number_input("Pack replacement cost (€)", min_value=1000.0, max_value=80000.0,
                                       value=12000.0, step=500.0,
                                       help="Used to price degradation: lost capacity is valued at €(cost)/kWh.")

    st.header("Daily driving schedule")
    n_trips = st.number_input("Number of trips per day", min_value=0, max_value=6, value=2, step=1)

    trips: list[Trip] = []
    default_starts = [7.5, 17.0, 12.0, 20.0, 9.0, 14.0]
    default_ends = [8.5, 18.0, 13.0, 21.0, 10.0, 15.0]
    for i in range(int(n_trips)):
        st.markdown(f"**Trip {i + 1}**")
        c1, c2 = st.columns(2)
        with c1:
            start_h = st.number_input(
                f"Start (hour of day)", min_value=0.0, max_value=23.99,
                value=default_starts[i] if i < len(default_starts) else 9.0,
                step=0.25, key=f"start_{i}",
            )
        with c2:
            end_h = st.number_input(
                f"End (hour of day)", min_value=0.0, max_value=23.99,
                value=default_ends[i] if i < len(default_ends) else 10.0,
                step=0.25, key=f"end_{i}",
            )
        intensity = st.radio(
            "Drive style", options=["slow", "fast"], horizontal=True, key=f"int_{i}",
            help="slow ≈ city/Landstraße (~15 kWh/100km), fast ≈ Autobahn (~22 kWh/100km).",
        )
        trips.append(Trip(start_h=float(start_h), end_h=float(end_h), intensity=intensity))

    st.header("Market parameters")
    feed_in_fee = st.slider("Feed-in fee (ct/kWh discharged)", 0.0, 10.0, 0.0, step=0.5,
                            help="Network charges / taxes on energy fed back to the grid. "
                            "Regulatory status unclear today (see § 19 StromNEV). Set to 0 for the "
                            "optimistic case, ~2-4 ct/kWh for a conservative scenario.")
    start_soc_pct = st.slider("Start-of-day SoC (%)", 20, 95, 70, step=5)

    run_btn = st.button("Run simulation", type="primary", use_container_width=True)


# ---------- Helper: daily preview ----------

profile = DailyProfile(trips=trips)
cons24 = profile.hourly_consumption()
total_daily_consumption = float(cons24.sum())

col1, col2, col3 = st.columns(3)
col1.metric("Daily driving energy", f"{total_daily_consumption:.1f} kWh")
col2.metric("Driving hours / day", f"{(cons24 > 0).sum()} h")
col3.metric("Idle hours / day", f"{(cons24 == 0).sum()} h")

st.subheader("Daily driving profile (hourly consumption)")
daily_df = pd.DataFrame({"hour": range(24), "kWh": cons24})
fig_day = px.bar(daily_df, x="hour", y="kWh",
                 labels={"hour": "Hour of day", "kWh": "Driving energy (kWh)"})
fig_day.update_layout(height=220, margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig_day, use_container_width=True)


# ---------- Run simulation ----------

@st.cache_data(show_spinner=False)
def _run_cached(
    capacity_kwh: float, power_kw: float, battery_cost_eur: float,
    trips_tuple: tuple, feed_in_fee_eur_kwh: float, start_soc_frac: float,
):
    profile = DailyProfile(trips=[Trip(s, e, i) for (s, e, i) in trips_tuple])
    battery = BatterySpec(capacity_kwh=capacity_kwh, power_kw=power_kw)
    cfg = SimConfig(
        battery=battery,
        daily_profile=profile,
        battery_cost_eur=battery_cost_eur,
        grid_feed_in_fee_eur_per_kwh=feed_in_fee_eur_kwh,
        start_soc_frac=start_soc_frac,
    )
    prices = load_prices()
    return run_year(cfg, prices), prices


if run_btn:
    if total_daily_consumption > capacity_kwh * 0.85:
        st.error(
            f"Your daily driving energy ({total_daily_consumption:.0f} kWh) is more than "
            f"85% of battery capacity ({capacity_kwh:.0f} kWh). Almost no spare capacity "
            "for V2G — and likely infeasible most days. Reduce trip length, increase "
            "capacity, or split into multiple charging sessions per day."
        )
        st.stop()

    trips_tuple = tuple((t.start_h, t.end_h, t.intensity) for t in trips)
    with st.spinner("Optimizing 365 days of dispatch against real 2025 day-ahead prices..."):
        result, prices = _run_cached(
            capacity_kwh, power_kw, battery_cost_eur, trips_tuple,
            feed_in_fee / 100.0, start_soc_pct / 100.0,
        )

    s = result.summary

    # ---------- Headline metrics ----------
    st.subheader("Annual outcome")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Net profit / year", f"€ {s['year_net_eur']:.0f}",
              help="Gross trading revenue minus battery wear cost (and any feed-in fee).")
    m2.metric("Gross revenue / year", f"€ {s['year_revenue_eur']:.0f}")
    m3.metric("Battery wear cost / year", f"€ {s['year_wear_eur']:.0f}")
    m4.metric("Extra capacity loss / year", f"{s['extra_capacity_loss_pct']:.2f} %",
              help="Capacity fade above the EV-only baseline (~1.5 %/yr). "
              "Based on NREL/EPRI V2G impact study.")

    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Avg net profit / day", f"€ {s['avg_daily_net_eur']:.2f}")
    m6.metric("Throughput / year", f"{s['total_throughput_kwh']:.0f} kWh")
    m7.metric("Wear cost / kWh throughput", f"{s['wear_cost_per_kwh']*100:.2f} ct")
    m8.metric("Infeasible days", f"{s['infeasible_days']}")

    if s["year_net_eur"] < 0:
        st.warning(
            "**Net profit is negative.** With these parameters, V2G earns less than "
            "the battery wear it causes. Try a higher charger power, a cheaper "
            "battery, or longer idle windows."
        )
    elif s["year_net_eur"] < 100:
        st.info("Net profit is positive but thin — V2G barely pays for itself in this scenario.")
    else:
        st.success(f"V2G adds **€{s['year_net_eur']:.0f}/yr** per vehicle after wear costs.")

    # ---------- Charts ----------
    daily = result.daily.copy()
    daily["month"] = daily.index.month
    daily["cum_net_eur"] = daily["net_profit_eur"].cumsum()

    st.subheader("Profit over time (2025)")
    tab1, tab2, tab3, tab4 = st.tabs(["Daily net €", "Cumulative €", "Monthly avg", "Weekday pattern"])

    with tab1:
        fig = px.bar(daily, x=daily.index, y="net_profit_eur",
                     labels={"x": "Date", "net_profit_eur": "Net profit (€)"})
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    with tab2:
        fig = px.area(daily, x=daily.index, y="cum_net_eur",
                      labels={"x": "Date", "cum_net_eur": "Cumulative net profit (€)"})
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    with tab3:
        monthly = daily.groupby("month")[["gross_revenue_eur", "wear_cost_eur", "net_profit_eur"]].mean()
        monthly.index = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(monthly)]
        fig = go.Figure()
        fig.add_bar(x=monthly.index, y=monthly["gross_revenue_eur"], name="Gross revenue")
        fig.add_bar(x=monthly.index, y=-monthly["wear_cost_eur"], name="Wear cost")
        fig.add_scatter(x=monthly.index, y=monthly["net_profit_eur"], mode="lines+markers",
                        name="Net (avg/day)", line=dict(color="black"))
        fig.update_layout(barmode="relative", height=350, yaxis_title="€ / day (monthly avg)")
        st.plotly_chart(fig, use_container_width=True)
    with tab4:
        daily["weekday"] = daily.index.dayofweek
        wk = daily.groupby("weekday")[["net_profit_eur"]].mean()
        wk.index = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        fig = px.bar(wk, y="net_profit_eur",
                     labels={"net_profit_eur": "Avg net profit (€ / day)", "index": "Weekday"})
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # ---------- Example day ----------
    st.subheader("Example day: best and worst")
    best_day = daily["net_profit_eur"].idxmax()
    worst_day = daily["net_profit_eur"].idxmin()
    c1, c2 = st.columns(2)
    for col, day, label in [(c1, best_day, "Best day"), (c2, worst_day, "Worst day")]:
        with col:
            st.markdown(f"**{label}: {day.date()} — net €{daily.loc[day, 'net_profit_eur']:.2f}**")
            day_h = result.hourly.loc[result.hourly.index.date == day.date()].copy()
            day_h["hour"] = day_h.index.hour
            fig = go.Figure()
            fig.add_bar(x=day_h["hour"], y=day_h["charge_kwh"], name="Charge (kWh)",
                        marker_color="#2E86AB")
            fig.add_bar(x=day_h["hour"], y=-day_h["discharge_kwh"], name="Discharge (kWh)",
                        marker_color="#F18F01")
            fig.add_scatter(x=day_h["hour"], y=day_h["price_eur_kwh"] * 100, name="Price (ct/kWh)",
                            yaxis="y2", line=dict(color="#444", dash="dot"))
            fig.add_scatter(x=day_h["hour"], y=day_h["soc_kwh"], name="SoC (kWh)",
                            yaxis="y3", line=dict(color="#A23B72"))
            fig.update_layout(
                height=350,
                yaxis=dict(title="kWh"),
                yaxis2=dict(title="ct/kWh", overlaying="y", side="right"),
                yaxis3=dict(title="SoC (kWh)", overlaying="y", side="right", position=0.95,
                            anchor="free"),
                barmode="relative",
                margin=dict(t=20, b=10),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ---------- Data footnote ----------
    st.divider()
    src = price_source()
    st.caption(
        f"Day-ahead prices: SMARD.de (Bundesnetzagentur), 2025 hourly, source = `{src}`. "
        f"Mean: {prices['price_eur_mwh'].mean():.1f} €/MWh, "
        f"min: {prices['price_eur_mwh'].min():.1f}, max: {prices['price_eur_mwh'].max():.1f}. "
        "Degradation model: NREL/EPRI V2G Impact Benchmark linear approximation "
        "(1.8 %/yr extra fade @ 43 % daily turnover)."
    )

else:
    st.info(
        "Configure your fleet on the left and hit **Run simulation**. "
        "The optimizer schedules charge/discharge across the whole of 2025 "
        "against real day-ahead prices, respecting your driving schedule and "
        "battery limits."
    )
