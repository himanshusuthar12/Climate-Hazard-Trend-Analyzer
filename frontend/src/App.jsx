import { useEffect, useState } from 'react'
import RegionMap from './components/RegionMap.jsx'
import { DaysChart, EventsChart, TmaxChart } from './components/Charts.jsx'
import { api, PRESETS } from './services/api.js'

export default function App() {
  const [city, setCity] = useState('')
  const [suggest, setSuggest] = useState([])
  const [lat, setLat] = useState('')
  const [lon, setLon] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [preset, setPreset] = useState('')
  const [hazard, setHazard] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    if (city.length < 3) { setSuggest([]); return }
    const t = setTimeout(async () => {
      try { setSuggest((await api.geocode(city)).results || []) } catch {}
    }, 350)
    return () => clearTimeout(t)
  }, [city])

  async function run() {
    const latitude = Number(lat)
    const longitude = Number(lon)
    const startYear = Number(start)
    const endYear = Number(end)

    if ([lat, lon, start, end, hazard].some((value) => value === '')) {
      setErr('Choose a location, hazard type, and year range before analyzing.')
      return
    }
    if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
      setErr('Latitude must be between -90 and 90.')
      return
    }
    if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
      setErr('Longitude must be between -180 and 180.')
      return
    }
    if (startYear < 1940 || endYear > 2025 || endYear < startYear || endYear - startYear > 60) {
      setErr('Choose years from 1940 to 2025, with an end year after the start and a maximum 60-year range.')
      return
    }

    setLoading(true)
    setErr('')
    try {
      const res = await api.analyze({
        lat: latitude,
        lon: longitude,
        start_year: startYear,
        end_year: endYear,
        hazard_type: hazard,
        label: city || `${latitude}, ${longitude}`,
      })
      setData(res)
    } catch (e) { setErr(String(e.message || e)) }
    finally { setLoading(false) }
  }

  const t = data?.trend_days
  return (
    <div className="layout">
      <header>
        <h1>🌡️ Climate Hazard Trend Analyzer</h1>
        <p>Heatwave frequency & intensity trends from Open-Meteo historical weather (1940–present). Click the map to pick any location.</p>
      </header>
      <div className="grid">
        <div>
          <div className="card">
            <h3>Region</h3>
            <label>City search</label>
            <input value={city} onChange={(e) => { setCity(e.target.value); setPreset('') }} placeholder="Search for a city" />
            {suggest.map((s, i) => (
              <button key={i} style={{ background: '#334155', marginTop: 6 }}
                onClick={() => {
                  setLat(String(s.lat))
                  setLon(String(s.lon))
                  setCity(`${s.name}, ${s.country || ''}`)
                  setPreset('')
                  setSuggest([])
                }}>
                {s.name}, {s.admin1 || ''} {s.country || ''} ({s.lat?.toFixed(2)}, {s.lon?.toFixed(2)})
              </button>
            ))}
            <label>Preset</label>
            <select value={preset} onChange={(e) => {
              const selectedPreset = e.target.value
              setPreset(selectedPreset)
              const place = PRESETS[Number(selectedPreset)]
              if (place) {
                setLat(String(place.lat))
                setLon(String(place.lon))
                setCity(place.label)
              }
            }}>
              <option value="">Choose a preset</option>
              {PRESETS.map((place, index) => <option key={place.label} value={index}>{place.label}</option>)}
            </select>
            <div className="row2">
              <div><label>Lat</label><input type="number" step="0.01" value={lat} onChange={(e) => setLat(e.target.value)} placeholder="Latitude" /></div>
              <div><label>Lon</label><input type="number" step="0.01" value={lon} onChange={(e) => setLon(e.target.value)} placeholder="Longitude" /></div>
            </div>
            <label>Hazard type</label>
            <select value={hazard} onChange={(e) => setHazard(e.target.value)}>
              <option value="">Choose a hazard type</option>
              <option value="heatwave">Heatwave</option>
            </select>
            <div className="row2">
              <div><label>Start year</label><input type="number" min="1940" max="2025" value={start} onChange={(e) => setStart(e.target.value)} placeholder="Start year" /></div>
              <div><label>End year</label><input type="number" min="1940" max="2025" value={end} onChange={(e) => setEnd(e.target.value)} placeholder="End year" /></div>
            </div>
            <button onClick={run} disabled={loading}>{loading ? 'Analyzing…' : 'Analyze'}</button>
            <p className="mut">Heatwave = 3+ consecutive days above the regional 95th percentile of daily Tmax.</p>
          </div>
          <div className="card">
            <h3>Map (click to select)</h3>
            <RegionMap
              lat={lat === '' ? null : Number(lat)}
              lon={lon === '' ? null : Number(lon)}
              onPick={(latitude, longitude) => {
                setLat(latitude.toFixed(3))
                setLon(longitude.toFixed(3))
              }}
            />
          </div>
        </div>
        <div>
          {err && <div className="err">⚠️ {err}</div>}
          {data && (
            <>
              <div className="card"><div className="summary">📌 {data.summary}</div>
                <div className="statgrid">
                  <div className="stat"><b>{data.threshold_c}°C</b><span>95th-pct threshold</span></div>
                  <div className="stat"><b>{t?.pct_change ?? '—'}%</b><span>change (last 5y vs first 5y)</span></div>
                  <div className="stat"><b>{t?.slope_per_year}</b><span>days / year slope</span></div>
                  <div className="stat"><b>{t?.direction}</b><span>MK p={t?.mann_kendall_p}</span></div>
                </div>
                <p className="mut">{data.baseline_note} Source: {data.meta?.source}. Cache: {data.meta?.cache} ({data.meta?.store}). Events found: {data.events_total}.</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <a href={api.csvUrl(data.cache_key)}><button>⬇ CSV</button></a>
                  <a href={api.pdfUrl(data.cache_key)}><button>⬇ PDF report</button></a>
                </div>
                {data.warnings?.map((w, i) => <div key={i} className="warn">⚠️ {w}</div>)}
              </div>
              <div className="card"><h3>Heatwave days per year + 5-yr rolling mean</h3><DaysChart yearly={data.yearly} trend={data.trend_days} /></div>
              <div className="card"><h3>Heatwave events per year</h3><EventsChart yearly={data.yearly} /></div>
              <div className="card"><h3>Mean annual max temperature</h3><TmaxChart yearly={data.yearly} /></div>
            </>
          )}
          {!data && !err && <div className="card mut">Enter a location and analysis period to view results.</div>}
        </div>
      </div>
      <p className="mut">Scope-over-polish build for Dygnify case study. Assumptions & methods in README. Data: Open-Meteo Archive (ERA5).</p>
    </div>
  )
}
