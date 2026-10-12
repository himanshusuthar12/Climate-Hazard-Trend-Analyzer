# Climate Hazard Trend Analyzer — Heatwave Edition

Analyzes historical heatwave trends for any location using real open data.

| Layer | Stack |
|---|---|
| Backend | Python 3.10+, FastAPI, numpy, httpx, pydantic, file-JSON NoSQL cache (MongoDB optional) |
| Frontend | React 18 + Vite, Chart.js, Leaflet (OpenStreetMap) |
| Data | **Open-Meteo Archive API** (ERA5, 1940–present, free, no key) |

## Quick start (2 terminals)

```bash
# 1) Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# → http://localhost:8000/api/health

# 2) Frontend
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

Windows one-liner: `run.bat` · Linux/Mac: `bash run.sh`. Docker: `docker compose up --build`.

## How it works

1. User picks a city (geocoded via Open-Meteo), a preset, map click, or lat/lon + year range (default **1990–2020**).
2. Backend fetches **daily Tmax** from Open-Meteo Archive, cleans outliers (`<-80` / `>60 °C` → NaN gap), computes the **95th percentile** threshold for that point/period.
3. **Heatwave = 3+ consecutive days with Tmax > threshold** (configurable percentile / min-days).
4. Yearly aggregation: events, heatwave-days, max duration, mean Tmax, mean exceedance. Trends: OLS slope, % change (last-5y mean vs first-5y mean), **Mann-Kendall** (tau, p, direction), 5-yr rolling mean (bonus).
5. Result cached as one NoSQL document per parameter-hash (MongoDB if `MONGO_URI` set, else `backend/cache/*.json` with 30-day TTL) and returned as JSON for charts + summary sentence like *“Heatwave days have increased by 40% …”*.
6. Bonus: Leaflet map picker, CSV + PDF export, MK test.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | store backend + time |
| GET | `/api/geocode?q=ahmed` | city search |
| POST | `/api/analyze` | `{lat, lon, start_year, end_year, threshold_percentile, min_consecutive_days, label}` or lat-lon box |
| GET | `/api/analyze?lat=..&lon=..&...` | same via query |
| GET | `/api/export/csv?cache_key=..` | yearly CSV |
| GET | `/api/export/pdf?cache_key=..` | PDF report |

Rate limit: 30 req/min/IP · CORS open for local dev · inputs validated (ranges, 60-yr window cap, label sanitized).

## Assumptions (stated per brief)

- Point analysis: a lat-lon **box uses its centre** (gridded ERA5 ~11 km; true areal averaging is future work).
- Percentile baseline = **full requested period** (stable, simple); a fixed 1990–2010 baseline option is trivial to add.
- Units °C; impossible values treated as honest gaps (warned in UI), not interpolated.
- Scope over polish: only **Heatwave** implemented; Drought/Rainfall are disabled options.

## Evaluation mapping

- **Data handling (20%)**: gap/outlier/unit handling, warnings, disk+Mongo cache, retries.
- **Climate logic (20%)**: percentile heatwave rule, yearly stats, rolling mean.
- **Backend (20%)**: clean FastAPI design, safe external calls, validation, tests.
- **Frontend (15%)**: Chart.js time-series + Leaflet map + insights.
- **Critical thinking (10%)**: honest MK significance + % context, no over-claiming.
- **Security+perf (15%)**: rate limit, TTL cache, input guards, timeouts.
- **Bonus (+10)**: map UI, CSV/PDF export, regression + Mann-Kendall.

## AI tools used

Muse Spark (via OpenCode) — scaffolding, trend math, UI wiring; all code executed and reviewed locally. Interview walkthrough ready.

## Repo layout

```
backend/  main.py climate_logic.py data_service.py database.py schemas.py rate_limit.py requirements.txt tests/
frontend/ src/{App.jsx main.jsx styles.css components/ services/} package.json vite.config.js index.html
README.md docker-compose.yml run.sh run.bat .gitignore
```
