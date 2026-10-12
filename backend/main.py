"""Climate Hazard Trend Analyzer — FastAPI backend.

Run:  pip install -r requirements.txt  →  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

load_dotenv()

from schemas import AnalyzeRequest
from data_service import fetch_daily_tmax, geocode_city
from climate_logic import (
    percentile_threshold,
    detect_heatwave_events,
    yearly_stats,
    build_trend,
    summary_sentence,
)
from database import store, make_cache_key
from rate_limit import is_rate_limited

app = FastAPI(title="Climate Hazard Trend Analyzer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"), "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _rate_limit_mw(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        if is_rate_limited(ip):
            return JSONResponse({"detail": "Rate limit exceeded (30/min). Try again shortly."}, status_code=429)
    return await call_next(request)


@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "store": store.backend, "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/geocode")
def geocode(q: str = Query(..., min_length=2, max_length=80)):
    return {"query": q, "results": geocode_city(q)}


def _run_analysis(req: AnalyzeRequest) -> dict:
    lat, lon = req.effective_point()
    key_payload = {
        "lat": round(lat, 3), "lon": round(lon, 3),
        "start": req.start_year, "end": req.end_year,
        "pct": req.threshold_percentile, "mcd": req.min_consecutive_days,
        "hz": req.hazard_type,
    }
    cache_key = make_cache_key(key_payload)
    cached = store.get(cache_key)
    if cached and cached.get("yearly"):
        doc = dict(cached)
        doc["meta"] = {**(doc.get("meta") or {}), "cache": "hit", "cache_key": cache_key}
        doc["cache_key"] = cache_key
        return doc

    dates, tmax, meta = fetch_daily_tmax(lat, lon, req.start_year, req.end_year)
    threshold = percentile_threshold(tmax, req.threshold_percentile)
    events = detect_heatwave_events(dates, tmax, threshold, req.min_consecutive_days)
    yearly, warnings = yearly_stats(dates, tmax, events)

    years = [y["year"] for y in yearly]
    days = [float(y["heatwave_days"]) for y in yearly]
    evts = [float(y["heatwave_events"]) for y in yearly]
    trend_days = build_trend(years, days, "heatwave_days_per_year")
    trend_events = build_trend(years, evts, "heatwave_events_per_year")

    label = req.label or f"{lat:.2f}°, {lon:.2f}°"
    if None not in (req.lat_min, req.lat_max, req.lon_min, req.lon_max):
        label = req.label or f"box-centre {lat:.2f}°, {lon:.2f}°"

    doc = {
        "cache_key": cache_key,
        "location": {
            "lat": lat, "lon": lon, "label": label,
            "box": (
                {"lat_min": req.lat_min, "lat_max": req.lat_max,
                 "lon_min": req.lon_min, "lon_max": req.lon_max}
                if req.lat_min is not None else None
            ),
            "start_year": req.start_year, "end_year": req.end_year,
        },
        "threshold_c": round(float(threshold), 2),
        "baseline_note": (
            f"{req.threshold_percentile:g}th percentile of daily Tmax over "
            f"{req.start_year}–{req.end_year} at this point (box uses centre)."
        ),
        "yearly": yearly,
        "events": events[:500],  # cap payload; full count preserved in yearly
        "events_total": len(events),
        "events_truncated": len(events) > 500,
        "trend_days": trend_days,
        "trend_events": trend_events,
        "summary": summary_sentence(label, trend_days, float(threshold)),
        "warnings": warnings,
        "meta": {**meta, "cache": "miss", "store": store.backend, "cache_key": cache_key},
    }
    store.set(cache_key, doc)
    return doc


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        return _run_analysis(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@app.get("/api/analyze")
def analyze_get(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    start_year: int = Query(default=1990, ge=1940, le=2025),
    end_year: int = Query(default=2020, ge=1940, le=2025),
    threshold_percentile: float = Query(default=95.0, ge=80, le=99.9),
    min_consecutive_days: int = Query(default=3, ge=2, le=10),
    label: str | None = Query(default=None, max_length=120),
):
    return analyze(AnalyzeRequest(
        lat=lat, lon=lon, start_year=start_year, end_year=end_year,
        threshold_percentile=threshold_percentile,
        min_consecutive_days=min_consecutive_days, label=label,
    ))


@app.get("/api/export/csv")
def export_csv(cache_key: str = Query(..., min_length=8, max_length=64)):
    doc = store.get(cache_key)
    if not doc:
        raise HTTPException(404, "Unknown/expired cache_key — run analysis first")
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["year", "heatwave_events", "heatwave_days", "max_duration_days", "mean_tmax", "mean_intensity_c"])
    w.writeheader()
    for row in doc.get("yearly", []):
        w.writerow({k: row.get(k) for k in w.fieldnames})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=heatwave_{cache_key}.csv"},
    )


@app.get("/api/export/pdf")
def export_pdf(cache_key: str = Query(..., min_length=8, max_length=64)):
    doc = store.get(cache_key)
    if not doc:
        raise HTTPException(404, "Unknown/expired cache_key — run analysis first")
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(500, "PDF extra not installed (pip install fpdf2)")

    def _latin(s: str) -> str:
        # Core PDF fonts are latin-1 only: replace em-dash/bullets/degree safely
        return (
            str(s).replace("—", "-").replace("–", "-").replace("°", " deg ")
            .encode("latin-1", errors="replace").decode("latin-1")
        )

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _latin("Climate Hazard Trend Analyzer - Heatwave Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    loc = doc.get("location", {})
    for line in [
        f"Location: {loc.get('label')} ({loc.get('lat')}, {loc.get('lon')})  {loc.get('start_year')}-{loc.get('end_year')}",
        f"Threshold: {doc.get('threshold_c')} C  |  {doc.get('baseline_note','')}",
        "",
        "Summary:",
        doc.get("summary", ""),
        "",
        f"Trend (days/yr): slope {doc['trend_days']['slope_per_year']}  pct {doc['trend_days']['pct_change']}%  "
        f"MK tau {doc['trend_days']['mann_kendall_tau']} p {doc['trend_days']['mann_kendall_p']} ({doc['trend_days']['direction']})",
        "",
        "Yearly table (year, events, days, maxDur, meanTmax):",
    ]:
        pdf.multi_cell(0, 7, _latin(line), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Courier", "", 9)
    for y in doc.get("yearly", []):
        pdf.cell(0, 5, f"{y['year']}  ev={y['heatwave_events']}  days={y['heatwave_days']}  max={y['max_duration_days']}  tmax={y['mean_tmax']}", new_x="LMARGIN", new_y="NEXT")
    out = bytes(pdf.output())
    return StreamingResponse(
        io.BytesIO(out),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=heatwave_{cache_key}.pdf"},
    )
