"""
step3_battery.py
================

SCHRITT 3: Das Akku-Modell (reine "Physik" / Energiebuchhaltung).

Hier wird NOCH NICHTS optimiert. Wir legen nur fest, wie sich der Ladestand
(SoC = State of Charge, "wie viele kWh sind im Akku") ueber die Zeit
veraendert, wenn man laedt, entlaedt und faehrt - und welche Grenzen gelten.

Das ist KEINE externe Bibliothek. Es ist simple Energieerhaltung:
in den Akku rein - aus dem Akku raus = Aenderung des Ladestands.

(Das KIT "bat-age-model" ist etwas ganz anderes: es berechnet die ALTERUNG
der Zelle. Das brauchen wir erst in Schritt 5, nicht hier.)


Die Groessen
------------
  capacity_kwh : Nennkapazitaet des Akkus in kWh (z.B. 75)
  power_kw     : maximale Lade- UND Entladeleistung in kW (z.B. 11)
  soc_min/max  : erlaubter Ladebereich, z.B. 10 % .. 90 % (schont den Akku)
  eff_charge / eff_discharge : Wirkungsgrade (one-way). Standard 1.0 = keine
                 Verluste (wie mit euch besprochen). Auf z.B. 0.95 setzen, um
                 das realistische ~10 % Roundtrip-Verlust-Szenario zu rechnen.


Energie pro Zeitschritt
-----------------------
Leistung mal Zeit = Energie:
      max. Energie pro 15-Min-Schritt = power_kw * 0.25 h
z.B. 11 kW * 0.25 h = 2.75 kWh pro Schritt.


Die SoC-Gleichung (pro Schritt t)
---------------------------------
      SoC[t+1] = SoC[t]
                 + eff_charge   * laden[t]       (Energie aus dem Netz)
                 - 1/eff_discharge * entladen[t] (Energie ins Netz)
                 - fahren[t]                     (Fahrverbrauch)

Mit Standard-Wirkungsgrad 1.0 wird daraus die einfache Bilanz:
      SoC[t+1] = SoC[t] + laden[t] - entladen[t] - fahren[t]

"laden[t]" und "entladen[t]" sind dabei die Energiemengen (kWh), die in
diesem Schritt mit dem Netz ausgetauscht werden.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import config
from .config import STEP_HOURS


@dataclass
class BatteryModel:
    # Standardwerte kommen jetzt zentral aus config.py
    capacity_kwh: float = config.BATTERY_CAPACITY_KWH
    power_kw: float = config.BATTERY_POWER_KW
    soc_min_frac: float = config.BATTERY_SOC_MIN_FRAC
    soc_max_frac: float = config.BATTERY_SOC_MAX_FRAC
    eff_charge: float = config.BATTERY_EFF_CHARGE
    eff_discharge: float = config.BATTERY_EFF_DISCHARGE

    # --- abgeleitete Groessen (Komfort) ---
    @property
    def soc_min_kwh(self) -> float:
        return self.soc_min_frac * self.capacity_kwh

    @property
    def soc_max_kwh(self) -> float:
        return self.soc_max_frac * self.capacity_kwh

    @property
    def max_energy_per_step_kwh(self) -> float:
        """Maximale Energie, die in EINEM 15-Min-Schritt geladen/entladen
        werden kann (Leistung * Schrittdauer)."""
        return self.power_kw * STEP_HOURS


@dataclass
class SocResult:
    """Ergebnis einer SoC-Simulation."""
    soc_kwh: np.ndarray              # Laenge N+1: SoC vor Schritt 0 ... nach Schritt N-1
    violations: list[str] = field(default_factory=list)  # Liste lesbarer Probleme

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0


def simulate_soc(
    charge_kwh: np.ndarray,        # (N,) Energie aus dem Netz pro Schritt
    discharge_kwh: np.ndarray,     # (N,) Energie ins Netz pro Schritt
    consumption_kwh: np.ndarray,   # (N,) Fahrverbrauch pro Schritt (aus Schritt 1)
    plugged_in: np.ndarray,        # (N,) bool: angesteckt? (aus Schritt 1)
    battery: BatteryModel,
    start_soc_kwh: float,
    check_limits: bool = True,
) -> SocResult:
    """Berechnet den SoC-Verlauf fuer einen GEGEBENEN Lade-/Entlade-Plan.

    Das ist die "Vorwaerts-Simulation": Plan rein -> SoC-Verlauf raus.
    Ausserdem werden Regelverstoesse gesammelt (zu leer, zu voll, laden ohne
    Stecker, Leistung ueberschritten). So koennen wir spaeter pruefen, ob ein
    vom Optimierer erzeugter Plan ueberhaupt zulaessig ist.
    """
    N = len(consumption_kwh)
    soc = np.zeros(N + 1, dtype=float)
    soc[0] = start_soc_kwh
    violations: list[str] = []

    max_step = battery.max_energy_per_step_kwh
    tol = 1e-6   # kleine Toleranz gegen Rundungsfehler

    for t in range(N):
        c = charge_kwh[t]
        d = discharge_kwh[t]

        if check_limits:
            # 1) Laden/Entladen nur, wenn angesteckt
            if (c > tol or d > tol) and not plugged_in[t]:
                violations.append(f"Schritt {t}: laden/entladen ohne Stecker")
            # 2) Leistungsgrenze pro Schritt
            if c > max_step + tol:
                violations.append(
                    f"Schritt {t}: laden {c:.3f} kWh > max {max_step:.3f} kWh/Schritt")
            if d > max_step + tol:
                violations.append(
                    f"Schritt {t}: entladen {d:.3f} kWh > max {max_step:.3f} kWh/Schritt")

        # SoC-Gleichung (mit Wirkungsgrad; bei 1.0 die einfache Bilanz)
        soc[t + 1] = (
            soc[t]
            + battery.eff_charge * c
            - (1.0 / battery.eff_discharge) * d
            - consumption_kwh[t]
        )

        if check_limits:
            # 3) Akku darf nicht zu leer / zu voll werden
            if soc[t + 1] < battery.soc_min_kwh - tol:
                violations.append(
                    f"Schritt {t}: SoC {soc[t+1]:.2f} kWh unter Minimum "
                    f"{battery.soc_min_kwh:.2f} kWh")
            if soc[t + 1] > battery.soc_max_kwh + tol:
                violations.append(
                    f"Schritt {t}: SoC {soc[t+1]:.2f} kWh ueber Maximum "
                    f"{battery.soc_max_kwh:.2f} kWh")

    return SocResult(soc_kwh=soc, violations=violations)
