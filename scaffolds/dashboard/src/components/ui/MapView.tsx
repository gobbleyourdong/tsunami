import { useEffect, useRef, useState } from "react"

interface Marker {
  lat: number
  lng: number
  label?: string
  popup?: string
  color?: string
}

interface MapViewProps {
  center?: [number, number]
  zoom?: number
  markers?: Marker[]
  onMarkerClick?: (marker: Marker) => void
  height?: number
  tileUrl?: string
}

export default function MapView({
  center = [51.505, -0.09],
  zoom = 13,
  markers = [],
  onMarkerClick,
  height = 400,
  tileUrl = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<any>(null)
  const [error, setError] = useState<string>("")
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    const loadLeaflet = async () => {
      try {
        // Dynamic import — Leaflet loaded at runtime
        const L = await import("leaflet")

        // Fix default marker icons (Leaflet CDN issue with bundlers)
        delete (L.Icon.Default.prototype as any)._getIconUrl
        L.Icon.Default.mergeOptions({
          iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
          iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
          shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
        })

        const map = L.map(containerRef.current!).setView(center, zoom)
        L.tileLayer(tileUrl, {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
          maxZoom: 19,
        }).addTo(map)

        markers.forEach(m => {
          const marker = L.marker([m.lat, m.lng]).addTo(map)
          if (m.popup || m.label) marker.bindPopup(m.popup || m.label || "")
          if (onMarkerClick) marker.on("click", () => onMarkerClick(m))
        })

        mapRef.current = map
        setLoaded(true)
      } catch {
        setError("Leaflet not installed. Run: npm install leaflet @types/leaflet")
      }
    }

    loadLeaflet()

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  if (error) {
    return (
      <div style={{
        height, display: "flex", alignItems: "center", justifyContent: "center",
        background: "var(--bg-secondary, #111827)", borderRadius: "var(--radius-md, 8px)",
        border: "1px solid var(--border, rgba(255,255,255,0.08))",
        color: "var(--text-secondary, #94a3b8)", fontSize: 13, padding: 20, textAlign: "center",
      }}>
        {error}
      </div>
    )
  }

  return (
    <div style={{ position: "relative", borderRadius: "var(--radius-md, 8px)", overflow: "hidden" }}>
      {!loaded && (
        <div style={{
          position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
          background: "var(--bg-secondary, #111827)", color: "var(--text-dim, #4a4f5e)", fontSize: 13, zIndex: 10,
        }}>
          Loading map...
        </div>
      )}
      <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
      <div ref={containerRef} style={{ height, width: "100%" }} />
    </div>
  )
}
