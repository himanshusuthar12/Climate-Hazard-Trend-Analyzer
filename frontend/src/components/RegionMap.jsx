import { MapContainer, TileLayer, Marker, Rectangle, useMapEvents } from 'react-leaflet'
import { useState } from 'react'

function ClickPick({ onPick }) {
  useMapEvents({ click(e) { onPick(e.latlng.lat, e.latlng.lng) } })
  return null
}

export default function RegionMap({ lat, lon, box, onPick }) {
  const [b, setB] = useState(box)
  const bounds = b ? [[b.lat_min, b.lon_min], [b.lat_max, b.lon_max]] : null
  return (
    <div className="mapbox">
      <MapContainer center={[lat || 20, lon || 0]} zoom={4} style={{ height: '100%', width: '100%' }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <ClickPick onPick={onPick} />
        {lat != null && <Marker position={[lat, lon]} />}
        {bounds && <Rectangle bounds={bounds} />}
      </MapContainer>
    </div>
  )
}
