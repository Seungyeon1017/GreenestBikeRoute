'use client'

import { cx } from 'class-variance-authority'
import { LocateFixed, ZoomOut } from 'lucide-react'
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
// Rough outline of the city of Heilbronn, [west, south, east, north].
const HEILBRONN_BOUNDS = [9.1, 49.08, 9.32, 49.22] as const
// Below this zoom, or with none of Heilbronn on screen, the view is "far" and
// the button offers to go back to Heilbronn. Inside Heilbronn but with its
// centre off-screen (zoomed in on one part), it offers to show the whole city.
const FAR_ZOOM = 10
const HINT_MS = 4000

type ViewState = 'home' | 'zoomed-in' | 'far'

function viewState(map: maplibregl.Map): ViewState {
  const view = map.getBounds()
  const [west, south, east, north] = HEILBRONN_BOUNDS
  const seesHeilbronn =
    view.getWest() < east &&
    view.getEast() > west &&
    view.getSouth() < north &&
    view.getNorth() > south
  if (map.getZoom() < FAR_ZOOM || !seesHeilbronn) {
    return 'far'
  }
  return view.contains(HEILBRONN_CENTER) ? 'home' : 'zoomed-in'
}
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
   * Show a button that flies back to the initial center and zoom: "Back to
   * Heilbronn" while the view is far away, "Show all of Heilbronn" while it is
   * zoomed in on one part of the city.
   */
  showRecenter?: boolean
  /**
   * Change this value (e.g. a counter) to highlight the recenter button for a
   * few seconds, if the view is far from Heilbronn at that moment.
   */
  recenterHint?: unknown
  /**
   * Bottom offset classes for the recenter button (default `bottom-10`, just
   * above the attribution), to keep it clear of other controls on the map.
   */
  recenterBottom?: string
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
  recenterBottom = 'bottom-10',
}: BaseMapProps) {
  const { t } = useTranslation()
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [view, setView] = useState<ViewState>('home')
  const [hinting, setHinting] = useState(false)
  const viewRef = useRef(view)
  viewRef.current = view

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

    map.on('moveend', () => setView(viewState(map)))

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

  // Highlight the button when the caller signals it, but only while far away:
  // zoomed in on Heilbronn, the new layer is already in view. The first render
  // isn't a signal.
  const firstHint = useRef(true)
  useEffect(() => {
    if (firstHint.current) {
      firstHint.current = false
      return
    }
    if (viewRef.current !== 'far') {
      return
    }
    setHinting(true)
    const timer = setTimeout(() => setHinting(false), HINT_MS)
    return () => clearTimeout(timer)
  }, [recenterHint])

  useEffect(() => {
    if (view !== 'far') {
      setHinting(false)
    }
  }, [view])

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
      {showRecenter && view !== 'home' && (
        <button
          className={cx(
            'absolute left-1/2 z-10 flex w-max max-w-[calc(100%-1.5rem)] -translate-x-1/2 items-center gap-2 rounded-full border px-4 py-2 text-center text-sm font-medium shadow-soft transition focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss',
            hinting
              ? 'border-leaf-forest bg-leaf-forest text-white ring-4 ring-leaf-mint'
              : 'border-leaf-sand bg-white text-leaf-forest hover:bg-leaf-cream',
            recenterBottom,
          )}
          onClick={recenter}
          type="button"
        >
          {view === 'far' ? (
            <LocateFixed aria-hidden className="h-4 w-4" />
          ) : (
            <ZoomOut aria-hidden className="h-4 w-4" />
          )}
          {hinting
            ? t('greenest.map.recenterHint')
            : view === 'far'
              ? t('greenest.map.recenter')
              : t('greenest.map.showAll')}
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
