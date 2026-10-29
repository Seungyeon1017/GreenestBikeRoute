'use client'

import type maplibregl from 'maplibre-gl'
import { useEffect, useRef } from 'react'
import BaseMap from '@/components/Greenest/Map'
import { drawLeisure, lineBounds } from './leisureLayers'

type RouteMapProps = {
  /** [lon, lat] of the route, or null for an empty map of Heilbronn. */
  coordinates: [number, number][] | null
  /** An upload not yet published: dashed. */
  draft?: boolean
  ariaLabel: string
}

/** A small map with one riders' route on it, fitted to the route. */
export default function RouteMap({
  coordinates,
  draft = false,
  ariaLabel,
}: RouteMapProps) {
  const mapRef = useRef<maplibregl.Map | null>(null)
  // The latest line, for when the map's style (re)loads after it changed.
  const lineRef = useRef({ coordinates, draft })
  lineRef.current = { coordinates, draft }

  function show(map: maplibregl.Map, fit: boolean) {
    const line = lineRef.current
    drawLeisure(map, line.coordinates, line.draft)
    if (fit && line.coordinates && line.coordinates.length >= 2) {
      map.fitBounds(lineBounds(line.coordinates), {
        padding: 40,
        maxZoom: 15,
        duration: 0,
      })
    }
  }

  useEffect(() => {
    if (mapRef.current) {
      show(mapRef.current, true)
    }
  }, [coordinates, draft])

  return (
    <div className="h-64 overflow-hidden rounded-2xl border border-leaf-sand md:h-80">
      <BaseMap
        ariaLabel={ariaLabel}
        onLoad={map => {
          mapRef.current = map
          show(map, true)
        }}
      />
    </div>
  )
}
