'use client'

import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { SenseBox } from '@/hooks/useOpenSenseMap'

const LIVE_THRESHOLD_MS = 60 * 60 * 1000 // 1 hour

function isLive(box: SenseBox): boolean {
  return (
    !!box.updatedAt &&
    Date.now() - new Date(box.updatedAt).getTime() < LIVE_THRESHOLD_MS
  )
}

interface OpenSenseMapMapProps {
  boxes: SenseBox[]
}

export default function OpenSenseMapMap({ boxes }: OpenSenseMapMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const { t } = useTranslation()

  useEffect(() => {
    if (!mapContainer.current || boxes.length === 0) {
      return
    }

    // If map already exists, just update markers
    if (mapRef.current) {
      return
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [
        boxes[0].currentLocation.coordinates[0],
        boxes[0].currentLocation.coordinates[1],
      ],
      zoom: 13,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      for (const box of boxes) {
        const [lng, lat] = box.currentLocation.coordinates

        const el = document.createElement('div')
        el.className = 'opensensemap-marker'
        el.style.width = '14px'
        el.style.height = '14px'
        el.style.borderRadius = '50%'
        el.style.backgroundColor = isLive(box) ? '#4ade80' : '#9ca3af'
        el.style.border = '2px solid white'
        el.style.boxShadow = '0 1px 4px rgba(0,0,0,0.3)'
        el.style.cursor = 'pointer'

        const popup = new maplibregl.Popup({ offset: 12 }).setHTML(
          `<div style="padding: 4px;">
            <strong>${box.name}</strong>
            <br/>
            <span style="font-size: 12px; color: #666;">
              ${box.sensors.length} Sensor${box.sensors.length !== 1 ? 'en' : ''}
            </span>
          </div>`,
        )

        new maplibregl.Marker({ element: el })
          .setLngLat([lng, lat])
          .setPopup(popup)
          .addTo(map)
      }

      // Fit bounds if multiple boxes
      if (boxes.length > 1) {
        const bounds = new maplibregl.LngLatBounds()
        for (const box of boxes) {
          bounds.extend(box.currentLocation.coordinates as [number, number])
        }
        map.fitBounds(bounds, { padding: 50 })
      }
    })

    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [boxes])

  return (
    <div className="relative h-full">
      <div
        className="min-h-[400px] w-full overflow-hidden rounded-lg lg:h-full"
        ref={mapContainer}
      />
      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-10 flex flex-col gap-1 rounded-md bg-white/90 px-2.5 py-2 text-xs shadow">
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full bg-green-400" />
          <span className="text-gray-700">{t('openSenseMap.liveData')}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 flex-shrink-0 rounded-full bg-gray-400" />
          <span className="text-gray-700">
            {t('openSenseMap.historicData')}
          </span>
        </div>
      </div>
    </div>
  )
}
