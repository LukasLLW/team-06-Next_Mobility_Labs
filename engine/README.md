# Plug & Earn — V2G-Ertragssimulation (`engine/`)

Berechnet, wie viel ein Elektroauto (bzw. eine Flotte) pro Jahr durch
Vehicle-to-Grid verdienen kann — auf Basis **echter Marktdaten 2025** und eines
**physikalischen Batterie-Alterungsmodells**, und zwar **ehrlich**: Erlöse
*minus* Batterieverschleiß.

Die Engine ist in 9 nachvollziehbare Schritte gegliedert. Jeder Schritt hat ein
eigenes Modul (`stepN_*.py`) und ein eigenes Testskript (`tests/test_stepN.py`),
das mit klaren `[OK]`/`[FEHLER]`-Meldungen prüft, ob der Schritt sinnvoll rechnet.

---

## Schnellstart

```bash
# Komplette Pipeline für ein Auto durchrechnen (Endergebnis):
python -m engine.run_demo --car 1 --pool 120

# Schnelle Tests (Schritt 1-3, keine langen Läufe):
python -m engine.tests.run_all

# Alle Tests (inkl. Optimierer + KIT-Modell, ~15 min):
python -m engine.tests.run_all --full

# Einzelnen Schritt testen:
python -m engine.tests.test_step7
```

---

## Die 9 Schritte

| Schritt | Modul | Was es tut |
|---|---|---|
| 1 | `step1_load_trips.py` | Fahrt-CSV einlesen → Jahres-Zeitleiste (Verbrauch / fährt / angesteckt) je 15 Min |
| 2 | `step2_load_prices.py` | SMARD Day-Ahead-Preise 2025 laden, auf 15-Min-Raster bringen |
| 3 | `step3_battery.py` | Akku-Modell: Ladestand (SoC), Lade-/Entladegrenzen, Wirkungsgrad |
| 4 | `step4_optimizer.py` | LP-Optimierer: wann laden/entladen für max. Gewinn (rollierend, kein Hellsehen) |
| 5 | `step5_degradation_kit.py` | KIT-Alterungsmodell: echte Kapazitätsfade, V2G vs. Baseline |
| 6 | `step6_net_profit.py` | Netto-Gewinn: Erlös − Degradationskosten (+ Verschleiß-Strafterm, Fallback) |
| 7 | `step7_load_fcr_prices.py` | FCR-Preise von regelleistung.net laden + ins LP einbauen |
| 8 | `step8_calibrate_wear.py` | Verschleiß-Strafterm k selbstkonsistent kalibrieren (Fixpunkt) |
| 9 | `step9_fcr_pool.py` | 1-MW-Mindestlosgröße: Aggregator-Pool, Cold-Start-Schwelle |

Datenfluss: alle Größen liegen auf **derselben 15-Min-Zeitleiste** (35.040
Schritte für 2025). `run_demo.py` ruft die Schritte in der richtigen Reihenfolge
auf.

---

## Die wichtigsten Modellannahmen

- **Zeitauflösung:** 15 Minuten; jeder Tag = 96 Schritte (DST wird im Fahrplan
  ignoriert, bei den Preisen sauber behandelt). Siehe `config.py`.
- **Akku (für alle Autos gleich, in `config.py`):** 75 kWh, 11 kW, SoC 10–90 %,
  **Wirkungsgrad 1,0** (verlustfrei — bewusst vereinfacht, Parameter vorhanden).
- **Day-Ahead = Plan *und* Abrechnung:** ein Preisdatensatz reicht. Realismus
  steckt im **rollierenden Horizont** (Optimierer sieht nur ~2 Tage voraus, kein
  Jahres-Hellsehen).
- **Degradation:** KIT-Modell (NMC/C-SiO-Zelle, echte Labordaten) bewertet den
  Plan physikalisch. Kosten = **End-of-Life-Modell**: Batterie ist bei
  `BATTERY_EOL_LOSS_PCT` (20 %) Verlust am Lebensende → jede verlorene %-Kapazität
  kostet `100/20 = 5×` mehr als beim simplen linearen Modell.
- **Verschleiß im Optimierer:** linearer Strafterm `k` pro kWh Durchsatz (das
  nichtlineare KIT-Modell passt nicht ins LP). `k` wird in Schritt 8
  selbstkonsistent kalibriert.
- **Baseline-Fallback:** Würde V2G netto Verlust machen, lässt man es bleiben
  (Netto 0). Der realisierbare Wert fällt nie unter 0.
- **FCR:** Verfügbarkeitszahlung (€/MW), symmetrischer SoC-Puffer für 15-Min-
  Vollabruf, Fahrt-Garantie bleibt erhalten. **Best case** = kein Abruf (kein
  Extra-Verschleiß), **worst case** = Dauer-Vollabruf. Echte Aktivierung läge
  dazwischen (stochastisches Frequenzprofil — bewusst noch nicht gebaut).
- **1-MW-Pool:** Ein Auto kann FCR nur im Aggregator-Pool ≥ 1 MW anbieten.
  Cold-Start-Schwelle bei 11 kW/Auto: ~91 Autos.

---

## Datenquellen (echt, Jahr 2025)

- **Day-Ahead-Preise:** SMARD.de (Bundesnetzagentur), Gebotszone DE-LU, stündlich.
  Bundeseinheitlich (keine Regionalunterschiede im Großhandel).
- **FCR-Preise:** regelleistung.net, 6 × 4-Stunden-Blöcke pro Tag, EUR/MW.
- **Batterie-Alterung:** KIT bat-age-model (`../bat-age-model/`, DOI 10.35097/1947).

Beide Preis-Loader cachen die Daten in `engine/data/` und haben einen
synthetischen Fallback, falls der Download scheitert.

---

## Was die Simulation zeigt (Kern-Narrativ)

Für ein Einzelauto mit dem Demo-Fahrprofil (nur nachts angesteckt):

1. **Naive Arbitrage** (kein Verschleiß-Bewusstsein) → **Verlustgeschäft**.
2. **+ Verschleiß-Management** (kalibrierter Strafterm) → nahe break-even.
3. **+ FCR** (Regelleistung) → **profitabel**.

Kernaussage: *V2G lohnt sich nur mit FCR und Verschleiß-Bewusstsein* — und das ist
hier mit echten Daten + physikalischem Alterungsmodell belegt, nicht behauptet.

---

## Abhängigkeiten

`numpy`, `pandas`, `scipy`, `pulp` (LP-Solver), `requests`, `openpyxl`
(FCR-xlsx). Das KIT-Modell unter `../bat-age-model/` wird automatisch importiert
(zwei kleine pandas-3-Kompatibilitäts-Fixes wurden dort vorgenommen).
