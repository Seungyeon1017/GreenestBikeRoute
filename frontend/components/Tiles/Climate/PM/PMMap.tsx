'use client'

import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import type { PMType, StationPM } from '@/hooks/useParticulateMatter'

// PM color scale thresholds (µg/m³) following EU air quality index
const PM_THRESHOLDS = [
  { max: 10, color: '#22c55e', label: 'Sehr gut' },
  { max: 20, color: '#84cc16', label: 'Gut' },
  { max: 35, color: '#eab308', label: 'Mäßig' },
  { max: 50, color: '#f97316', label: 'Schlecht' },
  { max: Infinity, color: '#ef4444', label: 'Sehr schlecht' },
]

function getColor(value: number | undefined): string {
  if (value === undefined) {
    return '#9ca3af'
  }
  for (const t of PM_THRESHOLDS) {
    if (value <= t.max) {
      return t.color
    }
  }
  return '#ef4444'
}

interface PMMapProps {
  stations: StationPM[]
  activePM: PMType
}

export default function PMMap({ stations, activePM }: PMMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<maplibregl.Marker[]>([])

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || stations.length === 0) {
      return
    }

    if (mapRef.current) {
      return
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: stations[0].coordinates,
      zoom: 13,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stations.length])

  // Update markers when stations or activePM changes
  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }

    // Remove existing markers
    for (const marker of markersRef.current) {
      marker.remove()
    }
    markersRef.current = []

    const addMarkers = () => {
      for (const station of stations) {
        const value = station.measurements[activePM]
        const color = getColor(value)

        const el = document.createElement('div')
        el.style.width = '20px'
        el.style.height = '20px'
        el.style.borderRadius = '50%'
        el.style.backgroundColor = color
        el.style.border = '2.5px solid white'
        el.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)'
        el.style.cursor = 'pointer'
        el.style.transition = 'background-color 0.3s'

        const displayValue =
          value !== undefined ? `${value.toFixed(1)} µg/m³` : 'Keine Daten'

        const popup = new maplibregl.Popup({ offset: 14 }).setHTML(
          `<div style="padding: 4px; min-width: 120px;">
            <strong>${station.boxName}</strong>
            <br/>
            <span style="font-size: 13px; color: ${color}; font-weight: 600;">
              ${activePM.replace('25', '2.5')}: ${displayValue}
            </span>
          </div>`,
        )

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(station.coordinates)
          .setPopup(popup)
          .addTo(map)

        markersRef.current.push(marker)
      }

      // Fit bounds
      if (stations.length > 1) {
        const bounds = new maplibregl.LngLatBounds()
        for (const s of stations) {
          bounds.extend(s.coordinates)
        }
        map.fitBounds(bounds, { padding: 50 })
      }
    }

    if (map.loaded()) {
      addMarkers()
    } else {
      map.on('load', addMarkers)
    }
  }, [stations, activePM])

  return (
    <div
      className="min-h-[500px] w-full overflow-hidden rounded-lg"
      ref={mapContainer}
    />
  )
}

export { PM_THRESHOLDS }
