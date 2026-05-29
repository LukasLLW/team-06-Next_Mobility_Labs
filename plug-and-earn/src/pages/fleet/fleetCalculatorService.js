/**
 * Berechnet das Flotten-Ergebnis basierend auf den UI-Eingaben,
 * transformiert sie in das vom Python-Backend (api.py) erwartete Format
 * und bricht die Ergebnisse auf Wochen-/Monatsbasis herunter.
 */
export async function calculateFleetResult({ vehicleTypes }) {
  // 1. UI-Daten in das JSON-Format für api.py (Variante A) transformieren
  const payload = {
    cars: [],
    use_fcr: true,
    include_daily: false,
    include_per_car: false,
    // Da wir die Laufzeit im UI nicht explizit wählen, nutzen wir einen stabilen Default 
    // (z. B. 1 Monat / 30 Tage), damit die Alterungsberechnung verlässlich ist.
    days: 30 
  };

  for (const vt of vehicleTypes) {
    // Bestimmung des CSV-Pfads oder des Fallback-Demofahrtenbuchs basierend auf dem Pattern
    let csvFile = "demodata/fahrtdaten_2025_01.csv"; // Standard-Fallback
    
    if (vt.hasCsv) {
      // HINWEIS: Echte Datei-Uploads müssten via FormData an einen API-Endpunkt geschickt werden,
      // der die Datei speichert und den Pfad zurückgibt. Wenn du lokal testest, mappen wir hier das Pattern:
      csvFile = `demodata/custom_upload_${vt.model}.csv`;
    } else {
      // Mapping deiner UI-Patterns auf deine Backend-Demofiles (Pfade anpassen!)
      const patternMapping = {
        delivery: "demodata/fahrtdaten_2025_01.csv",
        corporate: "demodata/fahrtdaten_2025_02.csv",
        municipal: "demodata/fahrtdaten_2025_01.csv",
        carsharing: "demodata/fahrtdaten_2025_02.csv",
        logistics: "demodata/fahrtdaten_2025_01.csv"
      };
      csvFile = patternMapping[vt.drivingPattern] || csvFile;
    }

    // Da api.py pro Eintrag in "cars" genau EIN Auto erwartet, du im UI aber "vehicleCount" hast,
    // duplizieren wir das Objekt entsprechend der Anzahl für die Flottensimulation.
    for (let i = 0; i < vt.vehicleCount; i++) {
      payload.cars.push({
        file: csvFile,
        battery: {
          capacity_kwh: vt.batteryCapacity,
          power_kw: vt.chargerPower,
          // cost_eur_per_kwh berechnet aus den UI-Gesamtkosten geteilt durch die Kapazität
          cost_eur_per_kwh: vt.batteryCapacity > 0 ? Math.round(vt.batteryCost / vt.batteryCapacity) : 150,
          soc_min_frac: 0.10, // Optionale Defaults aus api.py Spezifikation
          soc_max_frac: 0.90,
          eol_loss_pct: 20
        }
      });
    }
  }

  // 2. API-Request an dein Backend senden
  // (Passe die URL an dein Setup an, z.B. Express-Server, der api.py via Subprocess aufruft)
const response = await fetch("http://127.0.0.1:8000/api/simulate-fleet", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify(payload)
});

  if (!response.ok) {
    throw new Error(`Backend-Fehler: ${response.statusText}`);
  }

  const backendData = await response.json();
  
  if (!backendData.ok) {
    throw new Error(backendData.error || "Simulation fehlgeschlagen.");
  }

  // 3. Ergebnisse extrahieren und auf Zeiträume (Woche/Monat) herunterbrechen
  // Das Backend liefert aggregierte Gesamtwerte über den simulierten Zeitraum ("days") zurück.
  const simulatedDays = backendData.period.days || 30;
  const fleet = backendData.fleet;

  // Werte aus dem Backend holen
  const totalRevenue = fleet.trading_eur + fleet.fcr_eur;
  const totalDegradation = fleet.degradation_arbitrage_eur + fleet.degradation_fcr_worst_eur;
  const totalNet = fleet.net_best_eur; // Oder alternativ: totalRevenue - totalDegradation

  // Umrechnungsfaktoren
  const toWeek = 7 / simulatedDays;
  const toMonth = 30.4375 / simulatedDays; // Durchschnittliche Monatslänge

  return {
    week: {
      revenue: Math.round(totalRevenue * toWeek),
      degradationCost: Math.round(totalDegradation * toWeek),
      netProfit: Math.round(totalNet * toWeek)
    },
    month: {
      revenue: Math.round(totalRevenue * toMonth),
      degradationCost: Math.round(totalDegradation * toMonth),
      netProfit: Math.round(totalNet * toMonth)
    }
  };
}