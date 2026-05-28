"""
config.py
=========

Zentrale Konstanten fuer die gesamte Simulation.

Wir zerlegen das Jahr 2025 in gleich grosse Zeitschritte ("steps").
Ein Schritt ist standardmaessig 15 Minuten lang. Das passt:
  - zu den Fahrtzeiten in den CSV-Dateien (z.B. 7:30-8:15),
  - zur deutschen 15-Minuten-Abrechnung im Strommarkt (Bilanzkreis),
  - und Day-Ahead-Preise (stuendlich) lassen sich leicht auf 15-Min broadcasten.

WICHTIG zur Zeitrechnung:
  Wir behandeln jeden Kalendertag als GENAU 96 Schritte (96 * 15 min = 24 h).
  Damit ignorieren wir bewusst die Sommer-/Winterzeit-Umstellung (DST).
  Grund: Die Fahrtdaten sind in lokaler "Wanduhr"-Zeit ohne Zeitzone
  gespeichert, und ein fixes 96er-Raster ist viel einfacher und robuster.
  (Die Preis-Ausrichtung in Schritt 2 kuemmert sich separat um DST.)
"""

from __future__ import annotations

from datetime import date

# --- Zeitraster -------------------------------------------------------------

YEAR = 2025
STEP_MINUTES = 15                       # Laenge eines Zeitschritts in Minuten
STEPS_PER_HOUR = 60 // STEP_MINUTES     # = 4
STEPS_PER_DAY = 24 * STEPS_PER_HOUR     # = 96

YEAR_START = date(YEAR, 1, 1)
YEAR_END = date(YEAR, 12, 31)

# Anzahl Tage im Jahr 2025 (kein Schaltjahr -> 365)
N_DAYS = (YEAR_END - YEAR_START).days + 1   # = 365

# Gesamtzahl der Zeitschritte im ganzen Jahr
TOTAL_STEPS = N_DAYS * STEPS_PER_DAY        # = 35040

# Dauer eines Schritts in Stunden (nuetzlich fuer Energie<->Leistung)
STEP_HOURS = STEP_MINUTES / 60.0            # = 0.25


# --- Standard-Akku ----------------------------------------------------------
# Diese Werte gelten (der Einfachheit halber) fuer JEDES Auto gleich.
# Sie sind hier zentral abgelegt, damit man sie an EINER Stelle aendern kann.
#
# WICHTIG: Das sind gesetzte Platzhalter (typische Werte), KEINE aus den
# Challenge-Daten abgeleiteten Messwerte:
#   - 75 kWh : typische Mittelklasse-EV-Batterie (z.B. VW ID.4)
#   - 11 kW  : typische 3-phasige AC-Wallbox-Leistung
#   - 10..90%: ueblicher Schutz-Ladebereich (schont den Akku)
#   - Wirkungsgrad 1.0 = verlustfrei (bewusst weggelassen; Parameter bleibt
#     erhalten, falls wir spaeter ein konservatives Szenario mit ~0.95 wollen)

BATTERY_CAPACITY_KWH = 75.0      # Nennkapazitaet in kWh
BATTERY_POWER_KW = 11.0          # max. Lade-/Entladeleistung in kW
BATTERY_SOC_MIN_FRAC = 0.10      # nie unter 10 %
BATTERY_SOC_MAX_FRAC = 0.90      # nie ueber 90 %
BATTERY_EFF_CHARGE = 1.0         # Ladewirkungsgrad (1.0 = verlustfrei)
BATTERY_EFF_DISCHARGE = 1.0      # Entladewirkungsgrad (1.0 = verlustfrei)

# Start-Ladestand zu Jahresbeginn (Anteil der Kapazitaet)
BATTERY_START_SOC_FRAC = 0.70    # Auto startet das Jahr zu 70 % geladen

# Akku-Anschaffungs-/Ersatzkosten -> brauchen wir, um Kapazitaetsverlust in
# Euro zu bewerten (Schritt 6: Verschleiss-Strafterm + Netto-Gewinn).
BATTERY_COST_EUR_PER_KWH = 160.0   # typ. ~150-180 EUR/kWh fuer ein EV-Pack

# End-of-Life-Schwelle: ab wie viel % Kapazitaetsverlust gilt der Akku als
# "verbraucht" (Lebensende fuer den Fahrzeugeinsatz). Eine NMC-Batterie wird
# ueblicherweise bei ~80 % Restkapazitaet (= 20 % Verlust) getauscht.
# Bedeutung fuer die Kosten: Die gesamten Akkukosten verteilen sich auf NUR
# diese 20 % nutzbaren Kapazitaetsverlust - jede verlorene %-Kapazitaet ist
# also 100/20 = 5x teurer als beim simplen linearen Modell.
# (Auf 100.0 setzen -> altes lineares pro-rata-Modell.)
BATTERY_EOL_LOSS_PCT = 20.0

# FCR-Mindestlosgroesse: ein Gebot am FCR-Markt muss mindestens 1 MW gross
# sein (aggregierte Pools erlaubt). Ein einzelnes Auto (11 kW) kann das nur im
# Verbund mit anderen erreichen -> Aggregator-Pool.
FCR_MIN_LOT_MW = 1.0

