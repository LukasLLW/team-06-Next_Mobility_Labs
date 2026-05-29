from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.api import run_simulation


REPO_ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = REPO_ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


app = FastAPI(title="Plug & Earn Backend")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FrontendVehicleType(BaseModel):
    model: str | None = None
    batteryCost: float = 12000
    batteryCapacity: float = 77
    chargerPower: float = 21
    vehicleCount: int = 50
    drivingPattern: str | None = "corporate"
    hasCsv: bool | None = False
    uploadIndex: int | None = None


class FleetCalculationRequest(BaseModel):
    vehicleTypes: list[FrontendVehicleType]
    fromDate: str | None = "2025-06-01"
    days: int | None = 14
    useFcr: bool | None = True
    assumePoolSufficient: bool | None = True


def save_uploaded_file(upload: UploadFile) -> Path:
    original_name = Path(upload.filename or "fahrtenbuch.csv").name
    suffix = Path(original_name).suffix.lower()

    if suffix != ".csv":
        raise ValueError(f"Only CSV files are supported: {original_name}")

    safe_name = f"{uuid.uuid4().hex}_{original_name}"
    target_path = UPLOAD_DIR / safe_name

    with target_path.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    return target_path.resolve()


def build_engine_payload(
    request: FleetCalculationRequest,
    uploaded_paths: list[Path] | None = None,
) -> dict[str, Any]:
    vehicle_types = []
    uploaded_paths = uploaded_paths or []

    demo_logs_by_pattern = {
        "delivery": "demodata/fahrtdaten_2025_01.csv",
        "corporate": "demodata/fahrtdaten_2025_02.csv",
        "municipal": "demodata/fahrtdaten_2025_03.csv",
        "carsharing": "demodata/fahrtdaten_2025_04.csv",
        "logistics": "demodata/fahrtdaten_2025_05.csv",
    }

    fallback_logs = [
        "demodata/fahrtdaten_2025_01.csv",
        "demodata/fahrtdaten_2025_02.csv",
        "demodata/fahrtdaten_2025_03.csv",
        "demodata/fahrtdaten_2025_04.csv",
        "demodata/fahrtdaten_2025_05.csv",
        "demodata/fahrtdaten_2025_06.csv",
    ]

    for index, vehicle in enumerate(request.vehicleTypes):
        capacity_kwh = max(float(vehicle.batteryCapacity), 1.0)
        battery_cost_total = max(float(vehicle.batteryCost), 0.0)
        cost_eur_per_kwh = battery_cost_total / capacity_kwh

        log_path: str

        if (
            vehicle.hasCsv
            and vehicle.uploadIndex is not None
            and 0 <= vehicle.uploadIndex < len(uploaded_paths)
        ):
            log_path = str(uploaded_paths[vehicle.uploadIndex])
        else:
            log_path = demo_logs_by_pattern.get(
                vehicle.drivingPattern or "corporate",
                fallback_logs[index % len(fallback_logs)],
            )

        vehicle_types.append(
            {
                "count": max(int(vehicle.vehicleCount), 1),
                "log": log_path,
                "battery": {
                    "capacity_kwh": capacity_kwh,
                    "power_kw": max(float(vehicle.chargerPower), 0.0),
                    "soc_min_frac": 0.10,
                    "soc_max_frac": 0.90,
                    "cost_eur_per_kwh": cost_eur_per_kwh,
                    "eol_loss_pct": 20,
                },
            }
        )

    return {
        "vehicle_types": vehicle_types,
        "from_date": request.fromDate or "2025-06-01",
        "days": int(request.days or 14),
        "use_fcr": bool(request.useFcr),
        "assume_pool_sufficient": bool(request.assumePoolSufficient),
        "include_daily": False,
        "include_per_car": False,
    }


def map_engine_result_to_frontend(engine_result: dict[str, Any]) -> dict[str, Any]:
    if not engine_result.get("ok"):
        return {
            "ok": False,
            "error": engine_result.get("error", "Unknown backend error"),
        }

    fleet = engine_result["fleet"]
    week = fleet["per_week"]
    month = fleet["per_month"]

    return {
        "ok": True,
        "week": {
            "revenue": week["revenue_eur"],
            "degradationCost": week["degradation_eur"],
            "netProfit": week["net_best_eur"],
        },
        "month": {
            "revenue": month["revenue_eur"],
            "degradationCost": month["degradation_eur"],
            "netProfit": month["net_best_eur"],
        },
        "raw": engine_result,
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/fleet/calculate")
async def calculate_fleet(
    payload: str = Form(...),
    tripLogs: list[UploadFile] = File(default=[]),
) -> dict[str, Any]:
    try:
        request = FleetCalculationRequest.model_validate_json(payload)

        uploaded_paths = []
        for upload in tripLogs:
            uploaded_paths.append(save_uploaded_file(upload))

        engine_payload = build_engine_payload(request, uploaded_paths)
        engine_result = run_simulation(engine_payload)

        return map_engine_result_to_frontend(engine_result)

    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }