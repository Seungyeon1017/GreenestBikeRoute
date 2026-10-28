'use client'

import type { FeatureCollection } from 'geojson'
import maplibregl from 'maplibre-gl'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import { fetchRouteComparison } from '@/services/greenestApi'
import type {
  LngLat,
  Penalties,
  RouteComparison as RouteResult,
} from '@/types/greenest'
import RouteComparisonCard, { ROUTE_COLORS } from './RouteComparison'
import TripForm from './TripForm'

const INITIAL_PENALTIES: Penalties = { bump: 10, danger: 25, pm: 0.5 }

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** Creates the two route layers the first time, then puts the current result into them. */
function drawRoutes(map: maplibregl.Map, result: RouteResult | null) {
  if (!map.getSource('shortest')) {
    map.addSource('shortest', { type: 'geojson', data: EMPTY })
    map.addSource('greenest', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'shortest',
      type: 'line',
      source: 'shortest',
      paint: {
        'line-color': ROUTE_COLORS.shortest,
        'line-width': 5,
        'line-dasharray': [2, 2],
      },
    })
    map.addLayer({
      id: 'greenest',
      type: 'line',
      source: 'greenest',
      paint: { 'line-color': ROUTE_COLORS.greenest, 'line-width': 6 },
    })
  }
  map
    .getSource<maplibregl.GeoJSONSource>('shortest')
    ?.setData(result?.shortest ?? EMPTY)
  map
    .getSource<maplibregl.GeoJSONSource>('greenest')
    ?.setData(result?.route ?? EMPTY)
}

export default function PlanTripView() {
  const { t } = useTranslation()

  // 1. STATE: values that make the page redraw when they change.
  const [start, setStart] = useState<LngLat | null>(null)
  const [end, setEnd] = useState<LngLat | null>(null)
  const [penalties, setPenalties] = useState<Penalties>(INITIAL_PENALTIES)
  const [result, setResult] = useState<RouteResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  // 2. REFS: values kept between redraws that don't trigger a redraw themselves.
  const mapRef = useRef<maplibregl.Map | null>(null)
  const resultRef = useRef<RouteResult | null>(null)
  resultRef.current = result

  // 3. EFFECTS: code that runs when certain values change.

  // Ask the backend for a route when the points or sliders change.
  useEffect(() => {
    if (!start || !end) {
      return
    }
    const controller = new AbortController()
    setLoading(true)

    // Wait 300 ms after the last change, so dragging a slider sends one request, not dozens.
    const timer = setTimeout(() => {
      fetchRouteComparison(
        { from: start, to: end, penalties },
        controller.signal,
      )
        .then(data => {
          setResult(data)
          setError(null)
        })
        .catch(err => {
          if (err.name !== 'AbortError') {
            setResult(null)
            setError(err.message)
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setLoading(false)
          }
        })
    }, 300)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [start, end, penalties])

  // Draw (or clear) the two lines whenever a new result arrives.
  useEffect(() => {
    if (mapRef.current) {
      drawRoutes(mapRef.current, result)
    }
  }, [result])

  // Green pin at the start. The cleanup removes it when start changes or is reset.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !start) {
      return
    }
    const marker = new maplibregl.Marker({ color: '#1a7f37' })
      .setLngLat(start)
      .addTo(map)
    return () => {
      marker.remove()
    }
  }, [start])

  // Red pin at the destination.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !end) {
      return
    }
    const marker = new maplibregl.Marker({ color: '#b3261e' })
      .setLngLat(end)
      .addTo(map)
    return () => {
      marker.remove()
    }
  }, [end])

  // 4. HANDLERS: functions called by clicks and buttons.

  function handleMapClick(point: LngLat) {
    if (!start) {
      setStart(point)
    } else {
      setEnd(point)
    }
  }

  function handleReset() {
    setStart(null)
    setEnd(null)
    setResult(null)
    setError(null)
    setLoading(false)
  }

  // 5. RENDER: what appears on the page.
  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8">
      <PageIntro
        eyebrow={t('greenest.planTrip.eyebrow')}
        subtitle={t('greenest.planTrip.subtitle')}
        title={t('greenest.planTrip.title')}
      />
      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <TripForm
            end={end}
            loading={loading}
            onPenaltiesChange={setPenalties}
            onReset={handleReset}
            penalties={penalties}
            start={start}
          />
          {error && (
            <p
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800"
              role="alert"
            >
              {error}
            </p>
          )}
          <RouteComparisonCard result={result} />
        </div>
        <section className="h-[60vh] min-h-[420px] overflow-hidden rounded-3xl border border-leaf-sand shadow-soft lg:h-auto">
          <BaseMap
            ariaLabel={t('greenest.planTrip.mapLabel')}
            onClick={handleMapClick}
            onLoad={map => {
              mapRef.current = map
              drawRoutes(map, resultRef.current)
            }}
          />
        </section>
      </div>
    </div>
  )
}


/* 'use client'

import { Info } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import RouteComparison from './RouteComparison'
import TripForm, { type TripFormValues } from './TripForm'


const INITIAL_VALUES: TripFormValues = {
  start: '',
  destination: '',
  preferences: {
    preferGreener: true,
    preferQuieter: false,
    preferCycleLanes: true,
    maxExtraMinutes: 10,
  },
}

export default function PlanTripView() {
  const { t } = useTranslation()
  const [values, setValues] = useState(INITIAL_VALUES)
  // Address search and the call to services/greenestApi.fetchRoute arrive in Phase 4.
  const [submitted, setSubmitted] = useState(false)

  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8">
      <PageIntro
        eyebrow={t('greenest.planTrip.eyebrow')}
        subtitle={t('greenest.planTrip.subtitle')}
        title={t('greenest.planTrip.title')}
      />
      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <TripForm
            onChange={next => {
              setValues(next)
              setSubmitted(false)
            }}
            onSubmit={() => setSubmitted(true)}
            values={values}
          />
          {submitted && (
            <p
              className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
              role="status"
            >
              <Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              {t('greenest.planTrip.notConnected')}
            </p>
          )}
          <RouteComparison />
        </div>
        <section className="h-[60vh] min-h-[420px] overflow-hidden rounded-3xl border border-leaf-sand shadow-soft lg:h-auto">
          <BaseMap ariaLabel={t('greenest.planTrip.mapLabel')} />
        </section>
      </div>
    </div>
  )
}
 */