"""
test_step3.py
=============

Testskript fuer SCHRITT 3 (Akku-Modell / SoC-Physik).

Ausfuehren (vom Repo-Hauptordner aus):

    python -m engine.tests.test_step3

Jeder Test ist klein genug, um ihn mit dem Taschenrechner nachzurechnen.
So koennt ihr sicher sein, dass die Energiebilanz stimmt.
"""

from __future__ import annotations

import numpy as np

from engine.config import STEP_HOURS, STEPS_PER_DAY
from engine.step3_battery import BatteryModel, simulate_soc


def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "OK   " if condition else "FEHLER"
    line = f"  [{mark}] {name}"
    if detail:
        line += f"  ->  {detail}"
    print(line)


def test_1_nur_laden():
    """1 Stunde laden mit 11 kW (verlustfrei) -> SoC steigt um 11 kWh."""
    print("\nTest 1: 1 Stunde laden mit 11 kW (4 Schritte a 15 Min)")
    bat = BatteryModel(capacity_kwh=75, power_kw=11)
    N = 4  # 4 * 15 Min = 1 h
    energy_per_step = 11 * STEP_HOURS         # 11 kW * 0.25 h = 2.75 kWh
    charge = np.full(N, energy_per_step)
    discharge = np.zeros(N)
    consumption = np.zeros(N)
    plugged = np.ones(N, dtype=bool)

    res = simulate_soc(charge, discharge, consumption, plugged, bat, start_soc_kwh=30.0)
    gain = res.soc_kwh[-1] - res.soc_kwh[0]
    check("SoC-Zuwachs == 11.0 kWh", abs(gain - 11.0) < 1e-9,
          f"30.0 -> {res.soc_kwh[-1]:.2f} kWh (Zuwachs {gain:.2f})")
    check("keine Regelverstoesse", res.ok, f"{res.violations}")


def test_2_nur_fahren():
    """Einen ganzen Tag nur fahren (kein Laden) -> SoC sinkt um Tagesverbrauch."""
    print("\nTest 2: 1 Tag nur fahren, kein Laden")
    bat = BatteryModel(capacity_kwh=75, power_kw=11, soc_min_frac=0.0)
    N = STEPS_PER_DAY
    consumption = np.zeros(N)
    # Demo-Tagesverbrauch: 4.5 + 1.2 + 5.0 = 10.7 kWh, hier in 3 Schritte gelegt
    consumption[30] = 4.5
    consumption[48] = 1.2
    consumption[70] = 5.0
    charge = np.zeros(N)
    discharge = np.zeros(N)
    plugged = np.zeros(N, dtype=bool)

    res = simulate_soc(charge, discharge, consumption, plugged, bat, start_soc_kwh=60.0)
    drop = res.soc_kwh[0] - res.soc_kwh[-1]
    check("SoC-Verlust == 10.7 kWh", abs(drop - 10.7) < 1e-9,
          f"60.0 -> {res.soc_kwh[-1]:.2f} kWh (Verlust {drop:.2f})")
    check("keine Regelverstoesse", res.ok, f"{res.violations}")


def test_3_roundtrip():
    """Laden dann Entladen derselben Menge -> verlustfrei wieder am Start."""
    print("\nTest 3: 5.5 kWh laden, dann 5.5 kWh entladen (verlustfrei)")
    bat = BatteryModel(capacity_kwh=75, power_kw=11)
    charge = np.array([2.75, 2.75, 0.0, 0.0])
    discharge = np.array([0.0, 0.0, 2.75, 2.75])
    consumption = np.zeros(4)
    plugged = np.ones(4, dtype=bool)

    res = simulate_soc(charge, discharge, consumption, plugged, bat, start_soc_kwh=40.0)
    check("Endstand == Startstand (kein Verlust)", abs(res.soc_kwh[-1] - 40.0) < 1e-9,
          f"40.0 -> {res.soc_kwh[-1]:.2f} kWh")
    check("keine Regelverstoesse", res.ok, f"{res.violations}")


def test_3b_roundtrip_mit_wirkungsgrad():
    """Roundtrip MIT Wirkungsgrad 0.95: lade 5 kWh, entlade so, dass der Akku
    wieder auf Start ist -> ins Netz kommt weniger zurueck als man gekauft hat.
    Das ist der ~10 % Roundtrip-Verlust (0.95 * 0.95 = 0.9025)."""
    print("\nTest 3b: Roundtrip mit Wirkungsgrad 0.95 (zeigt den Verlust)")
    bat = BatteryModel(capacity_kwh=75, power_kw=11, eff_charge=0.95, eff_discharge=0.95)
    # Schritt 0: 5.0 kWh aus dem Netz -> 0.95*5.0 = 4.75 kWh landen im Akku.
    # Schritt 1: um die 4.75 kWh wieder aus dem Akku zu holen, kommen
    #            4.75 * 0.95 = 4.5125 kWh ins Netz.
    charge = np.array([5.0, 0.0])
    discharge = np.array([0.0, 4.5125])
    consumption = np.zeros(2)
    plugged = np.ones(2, dtype=bool)

    res = simulate_soc(charge, discharge, consumption, plugged, bat, start_soc_kwh=40.0)
    gekauft = charge.sum()
    verkauft = discharge.sum()
    roundtrip = verkauft / gekauft
    check("Akku wieder auf Startstand", abs(res.soc_kwh[-1] - 40.0) < 1e-6,
          f"40.0 -> {res.soc_kwh[-1]:.4f} kWh")
    check("Roundtrip-Wirkungsgrad == 0.9025 (= 0.95 * 0.95)",
          abs(roundtrip - 0.9025) < 1e-6,
          f"gekauft {gekauft:.4f} kWh, verkauft {verkauft:.4f} kWh -> {roundtrip:.4f}")
    print("       (Mit Wirkungsgrad verliert man also ~10 % pro Roundtrip - "
          "deshalb haben wir ihn fuers erste Modell weggelassen.)")


def test_4_grenzen_werden_erkannt():
    """Regelverstoesse muessen gemeldet werden."""
    print("\nTest 4: absichtliche Regelverstoesse -> muessen erkannt werden")
    bat = BatteryModel(capacity_kwh=75, power_kw=11, soc_min_frac=0.10, soc_max_frac=0.90)

    # a) Entladen ohne Stecker
    res_a = simulate_soc(np.array([0.0]), np.array([2.0]), np.array([0.0]),
                         np.array([False]), bat, start_soc_kwh=40.0)
    check("erkennt 'entladen ohne Stecker'",
          any("ohne Stecker" in v for v in res_a.violations), f"{res_a.violations}")

    # b) Leistung pro Schritt ueberschritten (5 kWh > 2.75 kWh moeglich)
    res_b = simulate_soc(np.array([5.0]), np.array([0.0]), np.array([0.0]),
                         np.array([True]), bat, start_soc_kwh=40.0)
    check("erkennt 'Leistung ueberschritten'",
          any("max" in v for v in res_b.violations), f"{res_b.violations}")

    # c) Akku zu leer (unter 10 % = 7.5 kWh)
    res_c = simulate_soc(np.array([0.0]), np.array([0.0]), np.array([5.0]),
                         np.array([False]), bat, start_soc_kwh=10.0)
    check("erkennt 'SoC unter Minimum'",
          any("unter Minimum" in v for v in res_c.violations), f"{res_c.violations}")


def main():
    print("=" * 70)
    print("SCHRITT 3 TEST: Akku-Modell (SoC-Physik)")
    print("=" * 70)
    print("Maximale Energie pro 15-Min-Schritt bei 11 kW:",
          f"{11 * STEP_HOURS:.2f} kWh")
    test_1_nur_laden()
    test_2_nur_fahren()
    test_3_roundtrip()
    test_3b_roundtrip_mit_wirkungsgrad()
    test_4_grenzen_werden_erkannt()
    print("\n" + "=" * 70)
    print("Fertig. Wenn oben alles [OK] ist, stimmt die Energiebilanz.")
    print("=" * 70)


if __name__ == "__main__":
    main()
