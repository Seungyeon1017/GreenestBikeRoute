'use client'

import { cx } from 'class-variance-authority'
import { LocateFixed } from 'lucide-react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { LngLat } from '@/types/greenest'

// Below this width the page scrolls past the map (no full-window layout), so
// one finger or the plain wheel scrolls the page and the map needs two
// fingers or Ctrl + scroll. Same breakpoint as Tailwind's `lg`.
const SCROLLING_PAGE_QUERY = '(max-width: 1023px)'

export const HEILBRONN_CENTER: LngLat = [9.2185, 49.1427]

// Zooming out stops at a view of Germany and its neighbours, enough to see
// where Heilbronn is, and panning stays within central Europe.
const MIN_ZOOM = 5
const MAX_BOUNDS: maplibregl.LngLatBoundsLike = [
  [-10, 40],
  [30, 60],
]
// Below this zoom, or with Heilbronn's centre off-screen, the map counts as
// "away" and offers the recenter button.
const AWAY_ZOOM = 10
const HINT_MS = 4000
// Same basemap as the existing dashboard maps (see components/Tiles/Climate/PM/PMMap.tsx).
const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'

// Plain background used when the basemap can't be loaded (e.g. offline).
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
  /**
   * Called after every style load, including after the fallback style is applied.
   * Add sources and layers here; check first whether they already exist.
   */
  onLoad?: (_map: maplibregl.Map) => void
  /** Called with [longitude, latitude] when the user clicks the map. */
  onClick?: (_point: LngLat) => void
  /**
   * Show a "Back to Heilbronn" button while the view is far from Heilbronn;
   * it flies back to the initial center and zoom.
   */
  showRecenter?: boolean
  /**
   * Change this value (e.g. a counter) to highlight the recenter button for a
   * few seconds, if the view is away from Heilbronn at that moment.
   */
  recenterHint?: unknown
}

/** MapLibre map centred on Heilbronn. Rendering and click events only, no data fetching. */
export default function BaseMap({
  className,
  center = HEILBRONN_CENTER,
  zoom = 13,
  ariaLabel,
  onLoad,
  onClick,
  showRecenter = false,
  recenterHint,
}: BaseMapProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [away, setAway] = useState(false)
  const [hinting, setHinting] = useState(false)
  const awayRef = useRef(away)
  awayRef.current = away

  // Store the latest callbacks in refs. The map is created once, so its event
  // handlers would otherwise keep calling the callbacks from the first render.
  const onLoadRef = useRef(onLoad)
  const onClickRef = useRef(onClick)
  onLoadRef.current = onLoad
  onClickRef.current = onClick

  useEffect(() => {
    if (!containerRef.current) {
      return
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center,
      zoom,
      minZoom: MIN_ZOOM,
      maxBounds: MAX_BOUNDS,
      attributionControl: { compact: true },
      cooperativeGestures: window.matchMedia(SCROLLING_PAGE_QUERY).matches,
      locale: {
        'CooperativeGesturesHandler.WindowsHelpText': t(
          'greenest.map.ctrlScroll',
        ),
        'CooperativeGesturesHandler.MacHelpText': t('greenest.map.cmdScroll'),
        'CooperativeGesturesHandler.MobileHelpText': t(
          'greenest.map.twoFingers',
        ),
      },
    })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    // 'style.load' fires after the first style and after every setStyle() call,
    // so layers added in onLoad survive the switch to the fallback style.
    map.on('style.load', () => onLoadRef.current?.(map))

    map.on('click', e => {
      onClickRef.current?.([e.lngLat.lng, e.lngLat.lat])
    })

    map.on('moveend', () => {
      setAway(
        map.getZoom() < AWAY_ZOOM ||
          !map.getBounds().contains(HEILBRONN_CENTER),
      )
    })

    map.once('error', () => {
      if (!map.isStyleLoaded()) {
        map.setStyle(FALLBACK_STYLE)
      }
    })

    mapRef.current = map
    return () => {
      mapRef.current = null
      map.remove()
    }
    // The map is created once; later prop changes reach it through the refs above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Highlight the button when the caller signals it, but only while away.
  // The first render isn't a signal.
  const firstHint = useRef(true)
  useEffect(() => {
    if (firstHint.current) {
      firstHint.current = false
      return
    }
    if (!awayRef.current) {
      return
    }
    setHinting(true)
    const timer = setTimeout(() => setHinting(false), HINT_MS)
    return () => clearTimeout(timer)
  }, [recenterHint])

  useEffect(() => {
    if (!away) {
      setHinting(false)
    }
  }, [away])

  const recenter = () => {
    mapRef.current?.flyTo({ center, zoom, essential: true })
  }

  return (
    <div className={cx('relative h-full w-full', className)}>
      <div
        aria-label={ariaLabel}
        className="h-full w-full"
        ref={containerRef}
        role="region"
      />
      {showRecenter && away && (
        <button
          className={cx(
            // Above the attribution line, which spans the bottom of narrow maps.
            'absolute bottom-10 left-1/2 flex w-max max-w-[calc(100%-1.5rem)] -translate-x-1/2 items-center gap-2 rounded-full border px-4 py-2 text-center text-sm font-medium shadow-soft transition focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss',
            hinting
              ? 'border-leaf-forest bg-leaf-forest text-white ring-4 ring-leaf-mint'
              : 'border-leaf-sand bg-white text-leaf-forest hover:bg-leaf-cream',
          )}
          onClick={recenter}
          type="button"
        >
          <LocateFixed aria-hidden className="h-4 w-4" />
          {hinting ? t('greenest.map.recenterHint') : t('greenest.map.recenter')}
        </button>
      )}
    </div>
  )
}

/* 'use client'

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

  ariaLabel: string

  onLoad?: (_map: maplibregl.Map) => void
}


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
 */
