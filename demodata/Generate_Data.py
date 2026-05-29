import csv
from datetime import date, datetime, timedelta

def generiere_fahrtdaten():
    # 1. Kopfzeile definieren
    header = ['time_start', 'time_end', 'consumed_kWh', 'charger_true_false']
    
    # 2. Zeitraum festlegen (Das gesamte Jahr 2025)
    start_datum = date(2025, 1, 1)
    end_datum = date(2025, 12, 31)
    
    # 3. Vorlage für die drei täglichen Fahrten erstellen
    # Format: (Start-Stunde, Start-Minute, End-Stunde, End-Minute, kWh, Charger)
    tages_fahrten = [
        (7, 30, 8, 15, 4.5, True),   # Morgens
        (12, 0, 12, 30, 1.2, False),  # Mittags
        (13, 0, 13, 30, 1.2, True),
        (17, 30, 18, 15, 5.0, True)   # Abends (z.B. danach ans Ladegerät angeschlossen)
    ]
    
    # Alle Zeilen für das Jahr sammeln
    alle_zeilen = []
    aktuelles_datum = start_datum
    
    # Schleife über jeden Tag im Jahr 2025
    while aktuelles_datum <= end_datum:
        for fahrt in tages_fahrten:
            start_h, start_m, end_h, end_m, kwh, charger = fahrt
            
            # Datum und Uhrzeit zusammensetzen
            time_start = datetime.combine(aktuelles_datum, datetime.min.time()).replace(hour=start_h, minute=start_m)
            time_end = datetime.combine(aktuelles_datum, datetime.min.time()).replace(hour=end_h, minute=end_m)
            
            # Als formatierten String in die Liste eintragen (Format: YYYY-MM-DD HH:MM:SS)
            alle_zeilen.append([
                time_start.strftime('%Y-%m-%d %H:%M:%S'),
                time_end.strftime('%Y-%m-%d %H:%M:%S'),
                kwh,
                charger
            ])
            
        # Einen Tag weiterzählen
        aktuelles_datum += timedelta(days=1)
        
    # 4. Die gesammelten Daten in 20 identische Dateien schreiben
    for i in range(1, 21):
        dateiname = f"fahrtdaten_2025_{i:02d}.csv"
        with open(dateiname, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(header)
            writer.writerows(alle_zeilen)
        print(f"Erfolgreich erstellt: {dateiname}")

if __name__ == "__main__":
    generiere_fahrtdaten()