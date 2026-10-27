'use client'

import { cx } from 'class-variance-authority'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef } from 'react'
import type { LngLat } from '@/types/greenest'

export const HEILBRONN_CENTER: LngLat = [9.2185, 49.1427]
// Same basemap as the existing dashboard maps (see components/Tiles/Climate/PM/PMMap.tsx).
const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

// Plain background used when the basemap can't be loaded (e.g. offline), so
// data layers added in onLoad still render.
const FALLBACK_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    {
      id: 'background',
      type: 'background',
      paint: { 'background-color': '#f5f5f4' },
    },
  ],
}

export type BaseMapProps = {
  className?: string
  center?: LngLat
  zoom?: number
  /** Accessible name for the map region. */
  ariaLabel: string
  /** Called once the style has loaded; add sources and layers here. */
  onLoad?: (_map: maplibregl.Map) => void
}

/** MapLibre map centred on Heilbronn. Rendering only, no data fetching. */
export default function BaseMap({
  className,
  center = HEILBRONN_CENTER,
  zoom = 13,
  ariaLabel,
  onLoad,
}: BaseMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const onLoadRef = useRef(onLoad)
  onLoadRef.current = onLoad

  useEffect(() => {
    if (!containerRef.current) {
      return
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center,
      zoom,
      attributionControl: { compact: true },
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => onLoadRef.current?.(map))
    map.once('error', () => {
      if (!map.isStyleLoaded()) {
        map.setStyle(FALLBACK_STYLE)
      }
    })

    return () => map.remove()
    // The map is created once; later prop changes are applied via onLoad callers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      aria-label={ariaLabel}
      className={cx('h-full w-full', className)}
      ref={containerRef}
      role="region"
    />
  )
}
