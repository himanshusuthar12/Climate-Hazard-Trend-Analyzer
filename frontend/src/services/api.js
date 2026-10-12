const BASE = import.meta.env.VITE_API_BASE || ''

async function j(res) {
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail || msg } catch {}
    throw new Error(msg)
  }
  return res.json()
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then(j),
  geocode: (q) => fetch(`${BASE}/api/geocode?q=${encodeURIComponent(q)}`).then(j),
  analyze: (body) => fetch(`${BASE}/api/analyze`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(j),
  csvUrl: (key) => `${BASE}/api/export/csv?cache_key=${key}`,
  pdfUrl: (key) => `${BASE}/api/export/pdf?cache_key=${key}`,
}

export const PRESETS = [
  { label: 'New Delhi, IN', lat: 28.61, lon: 77.21 },
  { label: 'Mumbai, IN', lat: 19.08, lon: 72.88 },
  { label: 'Ahmedabad, IN', lat: 23.03, lon: 72.58 },
  { label: 'Hyderabad, IN', lat: 17.39, lon: 78.49 },
  { label: 'Phoenix, US', lat: 33.45, lon: -112.07 },
  { label: 'London, UK', lat: 51.5, lon: -0.12 },
]
