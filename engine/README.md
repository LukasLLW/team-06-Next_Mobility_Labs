# Plug & Earn — V2G-Ertragssimulation (`engine/`)

Berechnet, wie viel ein Elektroauto pro Jahr durch **Vehicle-to-Grid** verdienen
kann — auf Basis **echter Marktdaten 2025** (Day-Ahead-Strompreise + FCR-Tender)
und eines **physikalischen Batterie-Alterungsmodells** (KIT). Und zwar
**ehrlich**: Erlöse *minus* Batterieverschleiß, mit transparenten Annahmen.

Die Engine ist in 10 nachvollziehbare Schritte gegliedert. Jeder Schritt hat ein
eigenes Modul (`stepN_*.py`) und ein eigenes Testskript (`tests/test_stepN.py`)
mit klaren `[OK]`/`[FEHLER]`-Meldungen.

---

## Schnellstart

```bash
# Komplette Pipeline für ein Auto, gewählter Zeitraum, k(SoC)-Modus:
python -m engine.run_demo --car 1 --from 2025-01-15 --days 14 --pool 120 --wear soc

# Ganzes Jahr, konstantes (Brent-optimiertes) k:
python -m engine.run_demo --car 1 --wear const

# Schnelle Tests (Schritt 1-3):
python -m engine.tests.run_all
# Alle Tests (inkl. Optimierer + KIT, ~15-20 min):
python -m engine.tests.run_all --full
```

### Web-App-Schnittstelle: `engine/api.py` (JSON rein, JSON raus)

Das ist der Einstiegspunkt für die Web-App. Aufruf per Subprocess
(`echo '<json>' | python -m engine.api`) oder aus Datei
(`python -m engine.api input.json`). Aus einer JS-App leicht in einen
Flask/FastAPI-Endpoint zu wrappen.

#### Vollständiges INPUT-Beispiel (alle Felder, mit Erklärung)

```jsonc
{
  // --- DIE FLOTTE als FAHRZEUG-TYPEN: pro Typ Logbuch + Akku + ANZAHL ---
  // Autos eines Typs sind identisch -> nur einmal gerechnet, mit count
  // gewichtet (schnell, auch bei 1000 Autos).
  "vehicle_types": [
    { "count": 30,                            // Anzahl Autos dieser Art
      "log": "demodata/fahrtdaten_2025_01.csv",
      "battery": {
        "capacity_kwh": 75,        // Nennkapazität des Akkus
        "power_kw": 22,            // max. Lade-/Entladeleistung
        "soc_min_frac": 0.10,      // nie unter 10 % laden (schont Akku)
        "soc_max_frac": 0.90,      // nie über 90 %
        "cost_eur_per_kwh": 160,   // AKKU-Kaufpreis pro kWh (NICHT Strompreis!)
        "eol_loss_pct": 20         // Akku-Lebensende bei 20 % Kapazitätsverlust
      } },
    { "count": 25, "log": "demodata/fahrtdaten_2025_02.csv",
      "battery": { "capacity_kwh": 60, "power_kw": 22, "cost_eur_per_kwh": 140 } }
  ],
  // Kurzform für Demo (N gleiche Autos): "car_count": 100, "battery": {...}

  // --- ZEITRAUM ---
  "from_date": "2025-06-01",       // Startdatum YYYY-MM-DD (Default: Jahresanfang)
  "days": 90,                      // Anzahl Tage (>=60 für belastbare Lebensdauer)

  // --- MARKT / V2G ---
  "use_fcr": true,                 // FCR (Regelleistung) mitvermarkten?
  "assume_pool_sufficient": false, // false = echter 1-MW-Check auf der Flotte
                                   //         (kleine Flotte -> evtl. kein FCR)
                                   // true  = Check aus, FCR immer einplanen

  // --- AUSGABE-DETAILTIEFE ---
  "include_daily": true,           // tägliche Zeitreihen mitgeben (für Charts)?
  "include_per_car": false         // Einzel-Typ-Details mitgeben? (sonst nur Flotte)
}
```

Alle Akku-Felder und alle Top-Level-Felder außer den Fahrzeug-Typen sind
**optional** — fehlt etwas, greifen die Defaults aus `config.py`.

#### Beispiel-OUTPUT (gekürzt)

```jsonc
{
  "ok": true,
  "period": { "from": "2025-06-01", "days": 90 },
  "data_sources": { "day_ahead": "smard", "fcr": "regelleistung.net" },
  "fcr_market": { "min_pool_size_for_1mw": 91,
                  "pool_marketable_fraction": 0.997, "peak_pool_mw": 1.32 },
  "fleet": {
    "n_cars": 2,
    "net_best_eur": ...,  "net_worst_eur": ...,        // Gesamt über alle Autos
    "trading_eur": ...,   "fcr_eur": ...,
    "degradation_arbitrage_eur": ..., "degradation_fcr_worst_eur": ...,
    "net_best_per_car_eur": ..., "net_best_per_car_eur_annualized": ...,
    "net_best_eur_annualized": ...,
    "battery_life_years": { "no_v2g": ..., "v2g_best": ..., "v2g_worst": ...,
                            "reliable": true }          // false bei < 60 Tagen
  },
  "daily_fleet": {                                       // nur bei include_daily
    "arbitrage_profit_eur": [...], "fcr_profit_eur": [...],
    "degradation_arbitrage_eur": [...], "degradation_fcr_worst_eur": [...],
    "net_best_eur": [...], "net_worst_eur": [...]        // je 1 Wert pro Tag
  }
  // "per_car": [...]                                    // nur bei include_per_car
}
```

Bei Fehler: `{ "ok": false, "error": "..." }`. Schnellster Smoke-Test:

```bash
echo '{"car_count": 3, "from_date": "2025-06-01", "days": 7, "assume_pool_sufficient": true, "include_daily": true}' | python -m engine.api
```

**Wichtig zu den zwei „€/kWh":** `cost_eur_per_kwh` (~160) ist der **Akku-Kaufpreis
pro kWh Kapazität** (für die Verschleißbewertung) — *nicht* der Strompreis. Die
Strompreise (~9 ct/kWh, variabel) kommen automatisch von SMARD.

### `run_demo`-Optionen
| Flag | Bedeutung | Default |
|---|---|---|
| `--car N` | Auto-Nummer (1–20) aus `demodata/` | 1 |
| `--from YYYY-MM-DD` | Startdatum des Zeitraums | Jahresanfang |
| `--days N` | Anzahl simulierter Tage | ganzes Jahr |
| `--pool N` | Autos im FCR-Aggregator-Pool (1-MW-Check) | unbegrenzt angenommen |
| `--wear const\|soc` | Verschleiß-Strafe: konstantes k vs. zeitvariables k(SoC) | const |
| `--no-fcr` | ohne FCR rechnen (nur Arbitrage) | aus |

---

## Die 10 Schritte

| # | Modul | Was es tut |
|---|---|---|
| 1 | `step1_load_trips.py` | Fahrt-CSV → Jahres-Zeitleiste (Verbrauch / fährt / angesteckt) je 15 Min |
| 2 | `step2_load_prices.py` | SMARD Day-Ahead-Preise 2025, auf 15-Min-Raster gebracht |
| 3 | `step3_battery.py` | Akku-Modell: Ladestand (SoC), Lade-/Entladegrenzen, Wirkungsgrad |
| 4 | `step4_optimizer.py` | LP-Optimierer: wann laden/entladen/FCR, rollierend (MPC, kein Hellsehen) |
| 5 | `step5_degradation_kit.py` | KIT-Alterungsmodell: echte Kapazitätsfade, V2G vs. Baseline |
| 6 | `step6_net_profit.py` | Netto-Gewinn: Erlös − Degradationskosten, Baseline-Fallback |
| 7 | `step7_load_fcr_prices.py` | FCR-Tender von regelleistung.net + ins LP einbauen |
| 8 | `step8_calibrate_wear.py` | Konstantes k per **Brent-1D-Optimierung** (max. Netto) |
| 9 | `step9_fcr_pool.py` | 1-MW-Mindestlosgröße: Aggregator-Pool, Cold-Start-Schwelle |
| 10 | `step10_soc_wear.py` | Zeitvariable Strafe **k(SoC)** statt eines globalen k |
| 11 | `step11_fleet.py` | Flotte: pro-Auto-Akkus, Pool-FCR aus echter Summe, tägliche Zeitreihen, Akku-Lebensdauer |

`run_demo.py` (Einzelauto, Text-Ausgabe) und `api.py` (Flotte, JSON-Ausgabe für
die Web-App) rufen die Schritte in der richtigen Reihenfolge auf. Alle Größen
liegen auf **derselben 15-Min-Zeitleiste** (96 Schritte/Tag).

---

## Wie der Optimierer funktioniert (Schritt 4)

Ein **lineares Programm (LP)**, das pro Zeitfenster *alle* Entscheidungen
gleichzeitig löst (nicht schrittweise). Variablen je Schritt: `laden`, `entladen`,
`SoC`, `fcr`. Zielfunktion (maximieren):

```
Σ  Preis·(entladen − laden)   ← Handelsgewinn
 − k·(laden + entladen)        ← Verschleiß-Strafe
 + FCR-Preis·fcr               ← FCR-Erlös
```

Nebenbedingungen: SoC-Kette, SoC-Grenzen 10–90 %, Leistungsteilung
(Arbitrage + FCR ≤ Lader), symmetrischer FCR-Puffer, „nur mit Stecker".

**Rollierend (MPC):** Fenster = 2 Tage, übernimm Tag 1, schiebe weiter — jeder
Tag wird mit dem aktuellsten Horizont neu geplant. So sieht der Optimierer nie
weiter als ~2 Tage voraus (realistisch, da Day-Ahead-Preise nur ~1 Tag im Voraus
feststehen).

**Fahrt-Garantie:** Der SoC darf nie unter das Minimum fallen — auch nicht
während einer Fahrt, auch nicht bei vollem FCR-Abruf. Damit ist jede geplante
Fahrt immer fahrbar.

---

## Die Verschleiß-Strafe k — zwei Modi (Schritte 8 & 10)

Das KIT-Alterungsmodell ist **nichtlinear** und passt nicht direkt ins LP.
Deshalb bildet ein **linearer Strafterm k** (€/kWh Durchsatz) den Verschleiß im
Optimierer ab. Zwei Wege, k zu bestimmen:

- **`const` (Schritt 8):** *ein* konstantes k, per **Brent-1D-Optimierung**
  gewählt — das k, das den (KIT-bewerteten) Netto-Gewinn maximiert. Gezielt und
  konvergent (kein blinder Sweep, kein instabiler Fixpunkt).
- **`soc` (Schritt 10):** zeitvariables **k(SoC(t))**. Einmal per KIT-Sweep
  kalibriert: „was kostet 1 kWh Durchsatz bei SoC=x an Alterung?". Ergebnis ist
  eine **U-Form** — Zyklen am SoC-Rand sind ~7× teurer als im mittleren Band:

  ```
  SoC 15% → ~22 ct/kWh   SoC 55% → ~3 ct/kWh   SoC 85% → ~20 ct/kWh
  ```
  Im LP bekommt dann jeder Schritt sein physikalisch motiviertes k. (Zirkularität
  — k braucht SoC, SoC kommt aus dem LP — wird über 1 Vorlauf + 1 finalen Lauf
  aufgelöst.) Liefert meist etwas bessere Bilanzen als das konstante k, weil der
  Optimierer Zyklen gezielt ins schonende mittlere SoC-Band legt.

---

## Wichtigste Modellannahmen (alle zentral in `config.py`)

- **Zeitauflösung:** 15 Min, jeder Tag = 96 Schritte (DST im Fahrplan ignoriert,
  bei den Preisen sauber behandelt).
- **Akku (für alle Autos gleich):** 75 kWh, 11 kW, SoC 10–90 %, **Wirkungsgrad
  1,0** (verlustfrei — bewusst vereinfacht, Parameter vorhanden).
- **Day-Ahead = Plan *und* Abrechnung.** Bundeseinheitlicher Großhandelspreis
  (keine Regionalunterschiede). Realismus über den rollierenden Horizont.
- **Degradationskosten = End-of-Life-Modell:** Batterie ist bei
  `BATTERY_EOL_LOSS_PCT` (20 %) Verlust am Lebensende → jede verlorene
  %-Kapazität kostet `100/20 = 5×` mehr als beim simplen linearen Modell.
- **Schonungs-Effekt wird ehrlich ausgewiesen:** Hält das intelligente Laden den
  Akku schonender als die Baseline (negative Mehralterung), zählt das als
  Gutschrift — kein Clipping, keine versteckten Boni.
- **FCR:** Verfügbarkeitszahlung (€/MW). Symmetrischer SoC-Puffer für 15-Min-
  Vollabruf; dadurch wird FCR automatisch ins schonende mittlere SoC-Band
  gedrückt. **Best case** = kein Abruf (kein Extra-Verschleiß), **worst case** =
  Dauer-Vollabruf. Echte Aktivierung läge dazwischen (stochastisches
  Frequenzprofil — bewusst noch nicht gebaut).
- **1-MW-Pool:** Ein Auto kann FCR nur im Aggregator-Pool ≥ 1 MW anbieten.
  Cold-Start-Schwelle bei 11 kW/Auto: ~91 Autos.
- **Baseline-Fallback:** Würde V2G netto Verlust machen, lässt man es bleiben
  (Netto 0). Der realisierbare Wert fällt nie unter 0.

---

## Datenquellen (echt, Jahr 2025)

- **Day-Ahead-Preise:** SMARD.de (Bundesnetzagentur), Gebotszone DE-LU, stündlich.
- **FCR-Preise:** regelleistung.net, 6 × 4-Stunden-Blöcke pro Tag (EUR/MW).
- **Batterie-Alterung:** KIT bat-age-model (`../bat-age-model/`, DOI 10.35097/1947).

Beide Preis-Loader cachen in `engine/data/` und haben einen synthetischen
Fallback, falls der Download scheitert.

---

## Kern-Narrativ (was die Simulation zeigt)

Für ein Einzelauto mit dem Demo-Fahrprofil (nur nachts angesteckt):

1. **Naive Arbitrage** ohne Verschleiß-Bewusstsein → **Verlustgeschäft**.
2. **+ Verschleiß-Management** (kalibriertes k) → nahe break-even; mit dem
   strengen EoL-Modell ist reine Day-Ahead-Arbitrage praktisch unwirtschaftlich.
3. **+ FCR** (Regelleistung, Aggregator-Pool ≥ 91 Autos) → **profitabel**.

Kernaussage: *V2G lohnt sich nur mit FCR und Verschleiß-Bewusstsein* — belegt mit
echten Daten und physikalischem Alterungsmodell, nicht behauptet.

---

## Stand & Ausbaurichtungen

**Fertig:** Schritte 1–10, alle getestet, dokumentiert, Zeitraum-Auswahl,
zwei k-Modi.

**Offen / dokumentierte Optionen:**
- **Flotten-Aggregation:** Einzelauto-Sim läuft für *jede* CSV; die Summierung
  über mehrere (unterschiedliche) Autos + Pool-FCR aus der echten Verfügbarkeits-
  Summe ist ein kleiner Zusatzschritt.
- **Stochastischer FCR-Abruf:** echtes/synthetisches Frequenzprofil → reale
  FCR-Verschleißzahl zwischen best/worst.
- **Adam/autodiff:** KIT-Modell in JAX portieren für gradientenbasierte
  Plan-Optimierung (Forschungsrichtung; Sequential LP / k(SoC) deckt das
  Wesentliche schon ab).
- **Sensitivität:** Depot-Profil (tagsüber Stecker → teure FCR-Blöcke), DC-Lader,
  LFP-Chemie.

---

## Abhängigkeiten

`numpy`, `pandas`, `scipy`, `pulp` (LP-Solver), `requests`, `openpyxl`
(FCR-xlsx). Das KIT-Modell unter `../bat-age-model/` wird automatisch importiert
(zwei kleine pandas-3-Kompatibilitäts-Fixes dort vorgenommen).
