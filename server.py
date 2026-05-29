# server.py
import sys
from pathlib import Path

# Sicherstellen, dass Python den "engine"-Ordner findet
sys.path.append(str(Path(__file__).resolve().parent))

from flask import Flask, request, jsonify
from flask_cors import CORS
from engine.api import run_simulation

app = Flask(__name__)
# CORS aktivieren, damit dein Frontend (Port 5173) zugreifen darf
CORS(app)

@app.route('/api/simulate-fleet', methods=['POST'])
def simulate_fleet_endpoint():
    try:
        # JSON-Daten aus dem Frontend holen
        payload = request.get_json()
        
        # Deine echte Simulation ausführen
        result = run_simulation(payload)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # Startet den Server auf Port 8000
    app.run(host='127.0.0.1', port=8000, debug=True)