"""
api.py  -  Das IO-Skript fuer die Web-App.

JSON rein, JSON raus. Entweder als Funktion (run_simulation) importieren oder
per Kommandozeile aufrufen (Subprocess aus der Web-App):

    python -m engine.api < input.json > output.json
    python -m engine.api input.json

--------------------------------------------------------------------------
INPUT (JSON)
--------------------------------------------------------------------------
{
  // Eine Flotte besteht aus FAHRZEUG-TYPEN. Pro Typ: Logbuch (CSV), Akku-Daten
  // und die ANZAHL Autos dieser Art. Autos eines Typs sind identisch -> werden
  // nur einmal gerechnet und mit count gewichtet (schnell, auch bei 1000 Autos).
  "vehicle_types": [
     {"count": 30, "log": "demodata/fahrtdaten_2025_01.csv",
      "battery": {"capacity_kwh": 75, "power_kw": 11, "soc_min_frac": 0.10,
                  "soc_max_frac": 0.90, "cost_eur_per_kwh": 160, "eol_loss_pct": 20}},
     {"count": 25, "log": "demodata/fahrtdaten_2025_02.csv",
      "battery": {"capacity_kwh": 60, "power_kw": 22, "cost_eur_per_kwh": 140}}
  ],
  // Alternativ (Kurzform fuer Demo): N gleiche Autos + ein Default-Akku
  // "car_count": 50,
  // "battery": { ... gilt als Default ... },

  "from_date": "2025-06-01",       // optional, Default Jahresanfang
  "days": 14,                      // optional, Default ganzes Jahr
  "use_fcr": true,
  "assume_pool_sufficient": false, // false = echter 1-MW-Check auf der Flotte
                                   //         (kleine Flotte -> evtl. kein FCR).
                                   // true  = Check aus, FCR immer einplanen
                                   //         (Annahme: Aggregator-Pool ist gross genug).
  "include_daily": true,           // taegliche Zeitreihen mitgeben?
  "include_per_car": false         // Einzel-Auto-Details mitgeben? (sonst nur Flotte)
}

Akku-Felder (alle optional, sonst config-Defaults):
  capacity_kwh, power_kw, soc_min_frac, soc_max_frac, cost_eur_per_kwh, eol_loss_pct

--------------------------------------------------------------------------
OUTPUT (JSON)  - Geld in EUR, Lebensdauer in Jahren
--------------------------------------------------------------------------
{
  "ok": true,
  "period": {"from": "...", "days": 14},
  "data_sources": {...},
  "fcr_market": {"min_pool_size_for_1mw", "pool_marketable_fraction", "peak_pool_mw"},
  "fleet": {                                  // ALLES als Flotten-Gesamt
     "n_cars",
     "net_best_eur", "net_worst_eur",         // gesamt
     "trading_eur", "fcr_eur",
     "degradation_arbitrage_eur", "degradation_fcr_worst_eur",
     "net_best_per_car_eur", "net_best_per_car_eur_annualized",
     "net_best_eur_annualized",
     "battery_life_years": {                  // Flotten-Schnitt
        "no_v2g", "v2g_best", "v2g_worst",
        "reliable": true|false,               // false bei kurzen Zeitraeumen
        "note": "..."                         // Hinweis, falls unzuverlaessig
     }
  },
  // nur wenn include_daily: ein Wert PRO TAG, ueber die Flotte summiert
  "daily_fleet": {
     "arbitrage_profit_eur":[...], "fcr_profit_eur":[...],
     "degradation_arbitrage_eur":[...], "degradation_fcr_worst_eur":[...],
     "net_best_eur":[...], "net_worst_eur":[...]
  },
  // nur wenn include_per_car: Einzel-Auto-Details (Liste)
  "per_car": [ {"battery", "net_best_eur", "net_worst_eur", "battery_life_years"} ]
}
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

# Repo-Hauptordner importierbar machen, falls die Datei direkt (statt als Modul)
# gestartet wird: `python engine/api.py` statt `python -m engine.api`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import config
from engine.config import STEPS_PER_DAY, YEAR_START, N_DAYS, FCR_MIN_LOT_MW
from engine.step1_load_trips import load_car_timeline
from engine.step2_load_prices import load_price_timeline, price_source
from engine.step3_battery import BatteryModel
from engine.step7_load_fcr_prices import load_fcr_timeline, fcr_source
from engine.step10_soc_wear import calibrate_k_of_soc, make_k_of_soc
from engine.step11_fleet import CarSpec, simulate_fleet

REPO = Path(__file__).resolve().parent.parent


def _build_battery(bdict: dict) -> tuple[BatteryModel, float, float]:
    """Akku-dict (mit config-Defaults) -> (BatteryModel, cost_per_kwh, eol_loss_pct)."""
    bat = BatteryModel(
        capacity_kwh=float(bdict.get("capacity_kwh", config.BATTERY_CAPACITY_KWH)),
        power_kw=float(bdict.get("power_kw", config.BATTERY_POWER_KW)),
        soc_min_frac=float(bdict.get("soc_min_frac", config.BATTERY_SOC_MIN_FRAC)),
        soc_max_frac=float(bdict.get("soc_max_frac", config.BATTERY_SOC_MAX_FRAC)),
    )
    cost = float(bdict.get("cost_eur_per_kwh", config.BATTERY_COST_EUR_PER_KWH))
    eol = float(bdict.get("eol_loss_pct", config.BATTERY_EOL_LOSS_PCT))
    return bat, cost, eol


def _abs(p: str) -> Path:
    pp = Path(p)
    return pp if pp.is_absolute() else REPO / pp


def _resolve_types(cfg: dict) -> list[tuple[Path, dict, int]]:
    """Gibt [(log_pfad, battery_dict, count), ...] zurueck - ein Eintrag pro
    Fahrzeug-TYP (mit Anzahl). Unterstuetzt drei Eingabeformen."""
    global_batt = cfg.get("battery", {})

    # Primaer: vehicle_types = [{count, log, battery}, ...]
    if cfg.get("vehicle_types"):
        out = []
        for t in cfg["vehicle_types"]:
            batt = {**global_batt, **t.get("battery", {})}
            out.append((_abs(t["log"]), batt, int(t.get("count", 1))))
        return out

    # Legacy: cars = einzelne Autos (je count 1)
    if cfg.get("cars"):
        return [(_abs(c["file"]), {**global_batt, **c.get("battery", {})}, 1)
                for c in cfg["cars"]]

    # Legacy/Demo: car_count gleiche Autos -> EIN Typ mit count=N (effizient,
    # da identisch -> nur einmal gerechnet)
    n = int(cfg.get("car_count", 1))
    return [(REPO / "demodata" / "fahrtdaten_2025_01.csv", global_batt, n)]


def run_simulation(cfg: dict) -> dict:
    # --- Zeitraum ---
    if cfg.get("from_date"):
        start_day = (date.fromisoformat(cfg["from_date"]) - YEAR_START).days
    else:
        start_day = 0
    n_days = int(cfg.get("days", N_DAYS - start_day))
    s, e = start_day * STEPS_PER_DAY, (start_day + n_days) * STEPS_PER_DAY

    use_fcr = bool(cfg.get("use_fcr", True))
    include_daily = bool(cfg.get("include_daily", False))
    include_per_car = bool(cfg.get("include_per_car", False))
    # Lebensdauer ist nur belastbar, wenn der Zeitraum lang genug ist (sonst
    # ueberschaetzt die initiale SEI-Bildungsrate die Alterung).
    RELIABLE_LIFE_MIN_DAYS = 60
    life_reliable = n_days >= RELIABLE_LIFE_MIN_DAYS

    # --- Marktdaten ---
    price = (load_price_timeline() / 1000.0)[s:e]
    fcr = (load_fcr_timeline() / 1000.0)[s:e] if use_fcr else None

    # --- Fahrzeug-Typen + pro-Typ-Akku + k(SoC) (mit Cache je Akku-Typ) ---
    types = _resolve_types(cfg)
    k_cache: dict = {}
    car_specs: list[CarSpec] = []
    for csv_path, bdict, count in types:
        _, tl = load_car_timeline(csv_path)
        bat, cost, eol = _build_battery(bdict)
        key = (bat.capacity_kwh, bat.power_kw, bat.soc_min_frac, bat.soc_max_frac, cost, eol)
        if key not in k_cache:
            grid, kv = calibrate_k_of_soc(bat, cost_per_kwh=cost, eol_loss_pct=eol)
            k_cache[key] = make_k_of_soc(grid, kv, bat.capacity_kwh)
        car_specs.append(CarSpec(
            consumption_kwh=tl.consumption_kwh[s:e], plugged_in=tl.plugged_in[s:e],
            battery=bat, cost_per_kwh=cost, eol_loss_pct=eol, k_func=k_cache[key],
            count=count))

    # --- Flotte simulieren ---
    fleet = simulate_fleet(car_specs, price, fcr,
                           assume_pool_sufficient=bool(cfg.get("assume_pool_sufficient", False)))

    annual = 365.0 / n_days
    week_f = 7.0 / n_days                 # Zeitraum -> auf eine Woche normiert
    month_f = (365.0 / 12.0) / n_days     # -> auf einen Monat (30.44 Tage) normiert
    power_kw_ref = car_specs[0].battery.power_kw

    # Aggregate fuer die Wochen-/Monats-Mittel (Flotte gesamt, BEST CASE - konsistent
    # mit net_best: im best case wird FCR nicht abgerufen -> nur Arbitrage-Verschleiss,
    # sodass net_best_eur = revenue_eur - degradation_eur gilt).
    revenue_total = fleet.total_trading_eur + fleet.total_fcr_eur
    degr_total = fleet.total_degradation_arbitrage_eur

    # Flotten-Durchschnitt der Akku-Lebensdauer (mit Anzahl gewichtet, endliche Werte)
    def _avg_life(attr):
        pairs = [(getattr(c, attr), sp.count) for sp, c in zip(car_specs, fleet.per_car)
                 if math.isfinite(getattr(c, attr))]
        if not pairs:
            return None
        wsum = sum(v * w for v, w in pairs)
        wtot = sum(w for _, w in pairs)
        return round(wsum / wtot, 1)

    out = {
        "ok": True,
        "period": {"from": str(YEAR_START.fromordinal(YEAR_START.toordinal() + start_day)),
                   "days": n_days},
        "data_sources": {"day_ahead": price_source().get("source"),
                         "fcr": fcr_source() if use_fcr else None},
        "fcr_market": {
            "min_pool_size_for_1mw": math.ceil(FCR_MIN_LOT_MW * 1000.0 / power_kw_ref),
            "pool_marketable_fraction": round(fleet.pool_marketable_fraction, 3),
            "peak_pool_mw": round(fleet.peak_pool_mw, 3),
        },
        "fleet": {
            "n_cars": fleet.n_cars,
            # --- Gesamt ueber alle Autos (EUR) ---
            "net_best_eur": round(fleet.total_net_best_eur, 1),
            "net_worst_eur": round(fleet.total_net_worst_eur, 1),
            "trading_eur": round(fleet.total_trading_eur, 1),
            "fcr_eur": round(fleet.total_fcr_eur, 1),
            "degradation_arbitrage_eur": round(fleet.total_degradation_arbitrage_eur, 1),
            "degradation_fcr_worst_eur": round(fleet.total_degradation_fcr_worst_eur, 1),
            # --- pro Auto im Schnitt + auf ein Jahr hochgerechnet ---
            "net_best_per_car_eur": round(fleet.avg_net_best_per_car_eur, 1),
            "net_best_per_car_eur_annualized": round(fleet.avg_net_best_per_car_eur * annual, 1),
            "net_best_eur_annualized": round(fleet.total_net_best_eur * annual, 1),
            # --- Akku-Lebensdauer (Flotten-Schnitt, Jahre) ---
            "battery_life_years": {
                "no_v2g": _avg_life("life_years_no_v2g"),
                "v2g_best": _avg_life("life_years_v2g_best"),
                "v2g_worst": _avg_life("life_years_v2g_worst"),
                "reliable": life_reliable,
                "note": (None if life_reliable else
                         f"grobe Hochrechnung aus {n_days} Tagen - fuer belastbare "
                         f"Werte >= {RELIABLE_LIFE_MIN_DAYS} Tage simulieren"),
            },
            # --- auf eine Woche / einen Monat normierte Mittelwerte (Flotte, BEST CASE) ---
            # Es gilt: net_best_eur = revenue_eur - degradation_eur
            "per_week": {
                "net_best_eur": round(fleet.total_net_best_eur * week_f, 1),
                "revenue_eur": round(revenue_total * week_f, 1),          # Arbitrage + FCR
                "degradation_eur": round(degr_total * week_f, 1),         # nur Arbitrage (best case)
            },
            "per_month": {
                "net_best_eur": round(fleet.total_net_best_eur * month_f, 1),
                "revenue_eur": round(revenue_total * month_f, 1),
                "degradation_eur": round(degr_total * month_f, 1),
            },
        },
    }

    if include_daily:
        out["daily_fleet"] = {k: [round(float(x), 3) for x in v]
                              for k, v in fleet.daily_fleet.items()}

    # Pro-Auto-Details nur auf ausdruecklichen Wunsch (sonst irrelevant bei vielen Autos)
    if include_per_car:
        out["per_car"] = [
            {
                "battery": {"capacity_kwh": sp.battery.capacity_kwh,
                            "power_kw": sp.battery.power_kw,
                            "cost_eur_per_kwh": sp.cost_per_kwh,
                            "eol_loss_pct": sp.eol_loss_pct},
                "net_best_eur": round(c.net_best_eur, 1),
                "net_worst_eur": round(c.net_worst_eur, 1),
                "battery_life_years": {
                    "no_v2g": _round_life(c.life_years_no_v2g),
                    "v2g_best": _round_life(c.life_years_v2g_best),
                    "v2g_worst": _round_life(c.life_years_v2g_worst),
                },
            }
            for sp, c in zip(car_specs, fleet.per_car)
        ]

    return out


def _round_life(years: float):
    return None if not math.isfinite(years) else round(years, 1)


def main():
    if len(sys.argv) > 1:
        cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        cfg = json.loads(sys.stdin.read())
    try:
        result = run_simulation(cfg)
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
