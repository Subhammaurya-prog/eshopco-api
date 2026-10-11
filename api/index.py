

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).resolve().parent.parent / "telemetry.json"


class RequestData(BaseModel):
    regions: list[str]
    threshold_ms: float = 180


def percentile(values, percent):
    values = sorted(values)

    if len(values) == 1:
        return values[0]

    position = (len(values) - 1) * percent / 100
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    fraction = position - lower

    return values[lower] + fraction * (
        values[upper] - values[lower]
    )


@app.post("/")
def calculate_metrics(request: RequestData):
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Could not read telemetry data"
        )

    result = {}

    for region in request.regions:
        matching = [
            record for record in records
            if record["region"] == region
        ]

        if not matching:
            raise HTTPException(
                status_code=404,
                detail=f"No records found for region: {region}"
            )

        latencies = [
            record["latency_ms"] for record in matching
        ]
        uptimes = [
            record["uptime_pct"] for record in matching
        ]

        result[region] = {
            "avg_latency": sum(latencies) / len(latencies),
            "p95_latency": percentile(latencies, 95),
            "avg_uptime": sum(uptimes) / len(uptimes),
            "breaches": sum(
                latency > request.threshold_ms
                for latency in latencies
            ),
        }

    return result
