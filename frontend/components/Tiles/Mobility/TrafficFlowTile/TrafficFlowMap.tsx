'use client'

import type { TrafficFlowFeatureCollection } from '@/hooks/useTrafficFlow'
import maplibregl from 'maplibre-gl'
import { useEffect, useRef } from 'react'

const LAYER_ID = 'traffic-flow-lines'
const SOURCE_ID = 'traffic-flow-source'

const COLOR_STOPS = [
  { threshold: 1, color: '#c7e9ff', label: '0-1' },
  { threshold: 3, color: '#7cc8ff', label: '2-3' },
  { threshold: 6, color: '#36a2eb', label: '4-6' },
  { threshold: 10, color: '#1f78d1', label: '7-10' },
  { threshold: 20, color: '#0c4da2', label: '11-20' },
  { threshold: Infinity, color: '#082b61', label: '> 20' },
]

const lineColorExpression: any[] = [
  'step',
  ['coalesce', ['to-number', ['get', 'points_in_segment']], 0],
  COLOR_STOPS[0].color,
  2,
  COLOR_STOPS[1].color,
  4,
  COLOR_STOPS[2].color,
  7,
  COLOR_STOPS[3].color,
  11,
  COLOR_STOPS[4].color,
  21,
  COLOR_STOPS[5].color,
]

interface TrafficFlowMapProps {
  collection: TrafficFlowFeatureCollection
}

export default function TrafficFlowMap({ collection }: TrafficFlowMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) {
      return
    }

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [9.221, 49.142],
      zoom: 12.5,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }

    const addOrUpdateLayer = () => {
      const source = map.getSource(SOURCE_ID) as
        | maplibregl.GeoJSONSource
        | undefined
      if (source) {
        source.setData(collection as any)
      } else {
        map.addSource(SOURCE_ID, {
          type: 'geojson',
          data: collection as any,
        })

        map.addLayer({
          id: LAYER_ID,
          type: 'line',
          source: SOURCE_ID,
          paint: {
            'line-color': lineColorExpression as any,
            'line-width': [
              'interpolate',
              ['linear'],
              ['zoom'],
              10,
              1.5,
              14,
              4,
              16,
              7,
            ],
            'line-opacity': 0.9,
          },
        })

        map.on('mouseenter', LAYER_ID, () => {
          map.getCanvas().style.cursor = 'pointer'
        })

        map.on('mouseleave', LAYER_ID, () => {
          map.getCanvas().style.cursor = ''
        })

        map.on('click', LAYER_ID, event => {
          const feature = event.features?.[0]
          if (!feature) {
            return
          }

          const props = feature.properties as {
            name?: string
            points_in_segment?: number | string
            road_segment?: number | string
          }

          const coordinates: [number, number] = event.lngLat
            ? [event.lngLat.lng, event.lngLat.lat]
            : [9.221, 49.142]

          const name = props?.name || 'Unbenanntes Segment'
          const points = props?.points_in_segment ?? 'n/a'
          const segment = props?.road_segment ?? 'n/a'

          new maplibregl.Popup({ closeButton: true, closeOnClick: true })
            .setLngLat(coordinates)
            .setHTML(
              `<div style="min-width:180px; padding:4px;">
                <strong>${name}</strong><br/>
                Segment: ${segment}<br/>
                Number Measurements: <strong>${points}</strong>
              </div>`,
            )
            .addTo(map)
        })
      }

      const bounds = new maplibregl.LngLatBounds()
      for (const feature of collection.features) {
        for (const coord of feature.geometry.coordinates) {
          bounds.extend(coord as [number, number])
        }
      }

      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, { padding: 40, maxZoom: 15 })
      }
    }

    if (map.loaded()) {
      addOrUpdateLayer()
    } else {
      map.once('load', addOrUpdateLayer)
    }
  }, [collection])

  return (
    <div className="relative h-[580px] w-full overflow-hidden rounded-lg bg-white">
      <div className="h-full w-full" ref={mapContainer} />

      <div className="absolute bottom-3 left-3 z-10 rounded-md bg-white/95 px-3 py-2 text-xs shadow">
        <div className="mb-1 font-semibold text-gray-700">Anzahl Messungen</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {COLOR_STOPS.map(stop => (
            <div className="flex items-center gap-1.5" key={stop.label}>
              <span
                className="inline-block h-2.5 w-3 rounded-sm"
                style={{ backgroundColor: stop.color }}
              />
              <span className="text-gray-700">{stop.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
