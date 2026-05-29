# Plug & Earn — V2G Revenue Simulation (`engine/`)

Simulates the annual revenue potential of Vehicle-to-Grid (V2G) operation for electric vehicles using:

* German 2025 day-ahead electricity prices (SMARD)
* FCR market data (`regelleistung.net`)
* A physics-based battery degradation model from KIT

The model evaluates **net profit**, including battery degradation costs.

The simulation pipeline is divided into modular steps. Each step has its own implementation (`stepN_*.py`) and test file (`tests/test_stepN.py`).

---

# Quick Start

```bash
# Run simulation for one vehicle over a selected period
python -m engine.run_demo --car 1 --from 2025-01-15 --days 14 --pool 120 --wear soc

# Full-year simulation with constant wear penalty
python -m engine.run_demo --car 1 --wear const

# Fast tests (steps 1–3)
python -m engine.tests.run_all

# Full test suite (~15–20 min)
python -m engine.tests.run_all --full
```

---

# Web API Interface (`engine/api.py`)

Main entry point for web applications.

Supports:

```bash
echo '<json>' | python -m engine.api
```

or

```bash
python -m engine.api input.json
```

The module can easily be wrapped in a Flask or FastAPI endpoint.

---

# Example Input

```jsonc
{
  "vehicle_types": [
    {
      "count": 30,
      "log": "demodata/driving_data_2025_01.csv",
      "battery": {
        "capacity_kwh": 75,
        "power_kw": 22,
        "soc_min_frac": 0.10,
        "soc_max_frac": 0.90,
        "cost_eur_per_kwh": 160,
        "eol_loss_pct": 20
      }
    },

    {
      "count": 25,
      "log": "demodata/driving_data_2025_02.csv",
      "battery": {
        "capacity_kwh": 60,
        "power_kw": 22,
        "cost_eur_per_kwh": 140
      }
    }
  ],

  "from_date": "2025-06-01",
  "days": 90,

  "use_fcr": true,
  "assume_pool_sufficient": false,

  "include_daily": true,
  "include_per_car": false
}
```

All battery parameters and all top-level fields except `vehicle_types` are optional. Missing values fall back to defaults defined in `config.py`.

---

# Example Output

```jsonc
{
  "ok": true,

  "period": {
    "from": "2025-06-01",
    "days": 90
  },

  "data_sources": {
    "day_ahead": "smard",
    "fcr": "regelleistung.net"
  },

  "fcr_market": {
    "min_pool_size_for_1mw": 91,
    "pool_marketable_fraction": 0.997,
    "peak_pool_mw": 1.32
  },

  "fleet": {
    "n_cars": 2,

    "net_best_eur": ...,
    "net_worst_eur": ...,

    "trading_eur": ...,
    "fcr_eur": ...,

    "degradation_arbitrage_eur": ...,
    "degradation_fcr_worst_eur": ...,

    "net_best_per_car_eur": ...,
    "net_best_per_car_eur_annualized": ...,

    "net_best_eur_annualized": ...,

    "battery_life_years": {
      "no_v2g": ...,
      "v2g_best": ...,
      "v2g_worst": ...,
      "reliable": true
    }
  },

  "daily_fleet": {
    "arbitrage_profit_eur": [...],
    "fcr_profit_eur": [...],

    "degradation_arbitrage_eur": [...],
    "degradation_fcr_worst_eur": [...],

    "net_best_eur": [...],
    "net_worst_eur": [...]
  }
}
```

Error format:

```json
{
  "ok": false,
  "error": "..."
}
```

Minimal smoke test:

```bash
echo '{"car_count": 3, "from_date": "2025-06-01", "days": 7, "assume_pool_sufficient": true, "include_daily": true}' | python -m engine.api
```

---

# `run_demo` Options

| Flag                | Description                    | Default       |
| ------------------- | ------------------------------ | ------------- |
| `--car N`           | Vehicle ID from `demodata/`    | `1`           |
| `--from YYYY-MM-DD` | Simulation start date          | Start of year |
| `--days N`          | Number of simulated days       | Full year     |
| `--pool N`          | Number of vehicles in FCR pool | Unlimited     |
| `--wear const\|soc` | Battery wear model             | `const`       |
| `--no-fcr`          | Disable FCR participation      | Off           |

---

# Simulation Pipeline

| Step | Module                     | Description                                              |
| ---- | -------------------------- | -------------------------------------------------------- |
| 1    | `step1_load_trips.py`      | Converts trip CSV into a 15-minute availability timeline |
| 2    | `step2_load_prices.py`     | Loads SMARD day-ahead prices and resamples to 15 min     |
| 3    | `step3_battery.py`         | Battery model: SoC, limits, charging/discharging         |
| 4    | `step4_optimizer.py`       | MPC-based LP optimizer for charging, discharging and FCR |
| 5    | `step5_degradation_kit.py` | KIT battery aging model                                  |
| 6    | `step6_net_profit.py`      | Net profit calculation including degradation             |
| 7    | `step7_load_fcr_prices.py` | Loads FCR tender prices                                  |
| 8    | `step8_calibrate_wear.py`  | Calibrates constant wear penalty `k`                     |
| 9    | `step9_fcr_pool.py`        | Aggregator pool and 1 MW threshold                       |
| 10   | `step10_soc_wear.py`       | SoC-dependent wear penalty `k(SoC)`                      |
| 11   | `step11_fleet.py`          | Fleet aggregation and fleet-level metrics                |

All simulations use a shared 15-minute timeline (96 steps/day).

---

# Optimization Model

The optimizer is formulated as a linear program (LP).

Decision variables per timestep:

* charging power
* discharging power
* state of charge (SoC)
* FCR reservation

Objective:

```text
maximize:

Σ price · (discharge − charge)
− k · throughput
+ FCR_price · FCR_capacity
```

Constraints include:

* SoC continuity
* SoC bounds
* charger power limits
* FCR reserve margins
* plug availability

The optimizer uses a rolling MPC horizon:

* optimize over 2 days
* execute day 1
* shift horizon forward

This avoids requiring long-term future price information.

---

# Battery Degradation Model

The KIT degradation model is nonlinear and therefore not directly embedded into the LP.

Instead, the optimizer uses a linear wear penalty:

```text
k [€/kWh throughput]
```

Two modes are available:

## `const`

Uses a single constant wear coefficient.

`k` is calibrated via Brent 1D optimization to maximize net profit under the KIT aging model.

## `soc`

Uses a time-dependent wear penalty:

```text
k(SoC)
```

The penalty is derived from KIT-based degradation sweeps across SoC levels.

Typical result:

```text
SoC 15% → ~22 ct/kWh
SoC 55% → ~3 ct/kWh
SoC 85% → ~20 ct/kWh
```

This encourages cycling in moderate SoC regions and generally improves net profitability compared to a constant penalty.

---

# Main Assumptions

Defined centrally in `config.py`.

* Time resolution: 15 min
* Default battery: 75 kWh, 11 kW
* SoC limits: 10–90%
* Charger efficiency: 100% (simplified)
* Day-ahead prices are used for both planning and settlement
* Battery end-of-life is defined at 20% capacity loss
* FCR modeled as symmetric reserve capacity
* Minimum FCR pool size: 1 MW
* Negative net-profit strategies are rejected (`net >= 0` fallback)

---

# Data Sources

* Day-ahead prices: SMARD (Bundesnetzagentur)
* FCR prices: `regelleistung.net`
* Battery degradation: KIT `bat-age-model`

Price loaders cache downloaded data in `engine/data/`.

Synthetic fallback data is available if downloads fail.

---

# Key Result

For the provided demo driving profile:

1. Pure day-ahead arbitrage is generally not profitable once degradation is included.
2. Wear-aware optimization improves results significantly.
3. FCR participation can make V2G economically viable at fleet scale.

---

# Dependencies

Required Python packages:

```text
numpy
pandas
scipy
pulp
requests
openpyxl
```

The KIT battery aging model is imported automatically from:

```text
../bat-age-model/
```
