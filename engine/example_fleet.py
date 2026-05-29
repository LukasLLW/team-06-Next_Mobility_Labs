"""
example_fleet.py  -  Vorlage: eine Flotte aus EIGENEN Logs + Akku-Saetzen rechnen.

Anpassen (die zwei markierten Stellen), dann:

    python -m engine.example_fleet

Es ruft dieselbe Logik wie die Web-Schnittstelle (engine.api.run_simulation) auf -
nur dass wir den Input hier in Python zusammenbauen statt als JSON zu schicken.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo-Hauptordner importierbar machen, egal wie das Skript gestartet wird
# (sowohl `python -m engine.example_fleet` als auch `python engine/example_fleet.py`)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.api import run_simulation


# ===========================================================================
# (1) DEINE FLOTTE als FAHRZEUG-TYPEN: pro Typ ein Logbuch (CSV), ein Akku-Satz
#     und die ANZAHL Autos dieser Art. Autos eines Typs sind identisch und
#     werden nur EINMAL gerechnet (mit count gewichtet) -> schnell, auch bei
#     vielen Autos. Hier 3 Typen mit insgesamt 30+25+25 = 80 Autos:
# ===========================================================================
vehicle_types = [
    {"count": 20, "log": "demodata/fahrtdaten_2025_01.csv",
     "battery": {"capacity_kwh": 75, "power_kw": 22, "soc_min_frac": 0.10,
                 "soc_max_frac": 0.90, "cost_eur_per_kwh": 160, "eol_loss_pct": 35}},
    {"count": 15, "log": "demodata/fahrtdaten_2025_02.csv",
     "battery": {"capacity_kwh": 60, "power_kw": 22, "soc_min_frac": 0.20,
                 "soc_max_frac": 0.80, "cost_eur_per_kwh": 140, "eol_loss_pct": 35}},
    {"count": 35, "log": "demodata/fahrtdaten_2025_03.csv",
     "battery": {"capacity_kwh": 90, "power_kw": 22, "soc_min_frac": 0.10,
                 "soc_max_frac": 0.90, "cost_eur_per_kwh": 180, "eol_loss_pct": 35}},
]

# So wuerdest du die Typen programmatisch aus eigenen Daten bauen:
#
#   import csv
#   vehicle_types = []
#   with open("meine_flotte.csv") as f:      # Tabelle: log, count, capacity_kwh, power_kw, ...
#       for row in csv.DictReader(f):
#           vehicle_types.append({
#               "count": int(row["count"]),
#               "log": f"meine_logs/{row['log']}",
#               "battery": {"capacity_kwh": float(row["capacity_kwh"]),
#                           "power_kw": float(row["power_kw"]),
#                           "cost_eur_per_kwh": float(row["cost_eur_per_kwh"]),
#                           "eol_loss_pct": float(row["eol_loss_pct"])},
#           })


# ===========================================================================
# (2) LAUF-EINSTELLUNGEN
# ===========================================================================
cfg = {
    "vehicle_types": vehicle_types,
    "from_date": "2025-06-01",     # Startdatum
    "days": 30,                    # Zeitraum (>=60 fuer belastbare Lebensdauer;
                                   #           ganzes Jahr = sehr rechenintensiv)
    "use_fcr": True,
    # 1-MW-Mindestlosgroesse: standardmaessig wird die ECHTE Flottenleistung
    # geprueft. Bei kleiner/schwacher Flotte (< 1 MW) faellt FCR dann weg.
    # Zum Erkunden des FCR-Potenzials einer kleinen Flotte: auf True setzen.
    "assume_pool_sufficient": False,
    "include_daily": True,         # taegliche Zeitreihen mitgeben
    "include_per_car": False,      # nur Flotten-Gesamt (True fuer Einzelauto-Details)
}


if __name__ == "__main__":
    result = run_simulation(cfg)

    # Kurz-Zusammenfassung auf den Bildschirm
    print(json.dumps(result["fleet"], indent=2, ensure_ascii=False))
    print("\nFCR-Markt:", result["fcr_market"])

    # KOMPLETTES Ergebnis (inkl. der taeglichen Zeitarrays in result["daily_fleet"])
    # in eine Datei schreiben - das ist, was die Web-App / Charts brauchen.
    out_path = Path(__file__).resolve().parent.parent / "fleet_result.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nKomplettes Ergebnis gespeichert in:\n  {out_path}")
    if "daily_fleet" in result:
        n = len(result["daily_fleet"]["net_best_eur"])
        print(f"  -> result['daily_fleet'] enthaelt je {n} Tageswerte:")
        print("     " + ", ".join(result["daily_fleet"].keys()))
