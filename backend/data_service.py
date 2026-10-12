"""Open-Meteo data access with caching, retries, gap/outlier handling.

Source: Open-Meteo Archive API (free, no key, 1940-present, daily Tmax).
Docs: https://open-meteo.com/en/docs/historical-weather-api
"""

from __future__ import annotations

import os
import time
import numpy as np
import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def fetch_daily_tmax(
    lat: float, lon: float, start_year: int, end_year: int, timeout: int = 30
) -> tuple[list[str], np.ndarray, dict]:
    """Returns (dates, tmax_array, meta). Raises RuntimeError on failure."""
    timeout = int(os.getenv("OPENMETEO_TIMEOUT", str(timeout)))
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_max",
        "timezone": "auto",
    }
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(ARCHIVE_URL, params=params)
                r.raise_for_status()
                data = r.json()
            daily = data.get("daily") or {}
            dates = daily.get("time") or []
            raw = daily.get("temperature_2m_max") or []
            tmax = np.array(
                [float(v) if v is not None else np.nan for v in raw], dtype=float
            )
            tmax = clean_tmax(tmax)
            meta = {
                "source": "Open-Meteo Archive API",
                "units": daily.get("units", "°C") if isinstance(daily.get("units"), str) else "°C",
                "queried_lat": params["latitude"],
                "queried_lon": params["longitude"],
                "n_days": len(dates),
            }
            if not dates:
                raise RuntimeError("Empty response from Open-Meteo")
            return dates, tmax, meta
        except Exception as e:  # retry with backoff
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo fetch failed after retries: {last_err}")


def clean_tmax(tmax: np.ndarray) -> np.ndarray:
    """Handle outliers/units: clip impossible values to NaN (honest gaps)."""
    out = tmax.astype(float).copy()
    # Physical plausibility for daily Tmax in °C
    out[(out < -80) | (out > 60)] = np.nan
    return out


def geocode_city(query: str, count: int = 5) -> list[dict]:
    q = (query or "").strip()[:80]
    if len(q) < 2:
        return []
    try:
        with httpx.Client(timeout=12) as client:
            r = client.get(
                GEOCODE_URL,
                params={"name": q, "count": max(1, min(count, 10)), "language": "en", "format": "json"},
            )
            r.raise_for_status()
            results = (r.json().get("results") or [])[:count]
            return [
                {
                    "name": x.get("name"),
                    "country": x.get("country"),
                    "admin1": x.get("admin1"),
                    "lat": x.get("latitude"),
                    "lon": x.get("longitude"),
                    "population": x.get("population"),
                }
                for x in results
            ]
    except Exception:
        return []
