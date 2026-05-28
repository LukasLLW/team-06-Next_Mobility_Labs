"""
run_all.py
==========

Fuehrt alle Schritt-Tests nacheinander aus.

    python -m engine.tests.run_all          # nur die schnellen Tests (Schritt 1-3, 9A)
    python -m engine.tests.run_all --full   # ALLE Tests (inkl. KIT + Optimierer, ~15 min)

Die schnellen Tests (ohne Optimierer-/KIT-Laeufe) sind gut fuer einen raschen
"laeuft noch alles?"-Check. --full rechnet die kompletten Jahres-Szenarien.
"""

from __future__ import annotations

import sys
import time
import importlib


# (Modulname, braucht_lange?)
QUICK = [
    "engine.tests.test_step1",   # Fahrtdaten einlesen
    "engine.tests.test_step2",   # Preise laden
    "engine.tests.test_step3",   # Akku-Modell
]
SLOW = [
    "engine.tests.test_step4",   # Optimierer (Jahreslauf)
    "engine.tests.test_step5",   # KIT-Degradation
    "engine.tests.test_step6",   # Verschleiss-Strafterm-Sweep
    "engine.tests.test_step7",   # FCR
    "engine.tests.test_step8",   # k-Kalibrierung + Fallback + FCR-Verschleiss
    "engine.tests.test_step9",   # EoL-Modell + 1-MW-Pool
]


def run(modules):
    results = []
    for mod_name in modules:
        print("\n" + "#" * 78)
        print(f"# {mod_name}")
        print("#" * 78)
        t0 = time.time()
        try:
            mod = importlib.import_module(mod_name)
            mod.main()
            ok = True
        except Exception as e:
            print(f"!!! FEHLER in {mod_name}: {type(e).__name__}: {e}")
            ok = False
        results.append((mod_name, ok, time.time() - t0))

    print("\n" + "=" * 78)
    print("ZUSAMMENFASSUNG")
    print("=" * 78)
    for name, ok, dt in results:
        mark = "OK   " if ok else "FEHLER"
        print(f"  [{mark}] {name:32s} ({dt:5.0f}s)")
    print("=" * 78)
    return all(ok for _, ok, _ in results)


def main():
    full = "--full" in sys.argv
    modules = QUICK + SLOW if full else QUICK
    if not full:
        print("Schnellmodus (nur Schritt 1-3). Fuer alle Tests: --full")
    ok = run(modules)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
