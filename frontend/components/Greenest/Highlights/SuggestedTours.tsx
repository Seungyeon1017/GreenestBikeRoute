'use client'

import { cx } from 'class-variance-authority'
import type { Feature, LineString } from 'geojson'
import {
  Bike,
  Bird,
  Clock,
  Download,
  type LucideIcon,
  MapPin,
  Moon,
  Mountain,
  Repeat,
  Route,
  Trees,
  Waves,
} from 'lucide-react'
import maplibregl from 'maplibre-gl'
import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card from '@/components/Greenest/ui/Card'
import { fetchTours } from '@/services/greenestApi'
import type {
  LngLat,
  TourCollection,
  TourId,
  TourProperties,
} from '@/types/greenest'
import { EXPERIENCES } from './content'

type Tour = Feature<LineString, TourProperties>

const TOUR_ICONS: Record<TourId, LucideIcon> = {
  scenicGreen: Trees,
  quietEscape: Moon,
  riverside: Waves,
  nature: Bird,
}

const SOURCE = 'tours'
const EMPTY = { type: 'FeatureCollection' as const, features: [] }

function percent(share: number) {
  return `${Math.round(share * 100)} %`
}

function bounds(tour: Tour) {
  const all = tour.geometry.coordinates as LngLat[]
  return all.reduce(
    (b, point) => b.extend(point),
    new maplibregl.LngLatBounds(all[0], all[0]),
  )
}

/** Plan trip reads `to` (lng,lat) and `name` and sets that place as the destination. */
function rideToStartHref(tour: Tour) {
  const start = tour.properties.stops[0]
  const query = new URLSearchParams({
    to: `${start.lon},${start.lat}`,
    name: start.name,
  })
  return `/plan-trip?${query}`
}

function escapeXml(text: string) {
  return text.replace(
    /[<>&"]/g,
    c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' })[c]!,
  )
}

/** The tour as GPX 1.1, for bike computers and navigation apps: its stops as waypoints, the line as a track. */
function tourGpx(tour: Tour, title: string) {
  const name = escapeXml(title)
  const stops = tour.properties.stops
    .map(
      s =>
        `  <wpt lat="${s.lat}" lon="${s.lon}"><name>${escapeXml(s.name)}</name></wpt>`,
    )
    .join('\n')
  const points = tour.geometry.coordinates
    .map(([lon, lat]) => `      <trkpt lat="${lat}" lon="${lon}"/>`)
    .join('\n')
  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Greenest Bike Route" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata><name>${name}</name></metadata>
${stops}
  <trk><name>${name}</name><type>cycling</type>
    <trkseg>
${points}
    </trkseg>
  </trk>
</gpx>
`
}

function downloadGpx(tour: Tour, title: string) {
  const blob = new Blob([tourGpx(tour, title)], {
    type: 'application/gpx+xml',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${tour.properties.id}.gpx`
  a.click()
  URL.revokeObjectURL(url)
}

/** A pill on the map at the tour's start or finish. */
function endMarker(lngLat: number[], label: string, start: boolean) {
  const el = document.createElement('div')
  el.className = cx(
    'rounded-full px-2.5 py-1 text-xs font-semibold shadow-soft ring-2',
    start
      ? 'bg-leaf-forest text-leaf-cream ring-white'
      : 'bg-white text-leaf-forest ring-leaf-forest',
  )
  el.textContent = label
  return new maplibregl.Marker({
    element: el,
    anchor: 'bottom',
    offset: [0, -6],
  }).setLngLat(lngLat as LngLat)
}

/** Adds the tour layers the first time (and after a style reload), then puts the tours into them. */
function drawTours(
  map: maplibregl.Map,
  tours: TourCollection,
  selected: TourId | null,
) {
  if (!map.getSource(SOURCE)) {
    map.addSource(SOURCE, { type: 'geojson', data: EMPTY, promoteId: 'id' })
    map.addLayer({
      id: `${SOURCE}-casing`,
      type: 'line',
      source: SOURCE,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#ffffff',
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          11,
          6,
        ],
      },
    })
    map.addLayer({
      id: SOURCE,
      type: 'line',
      source: SOURCE,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          '#1f3d2b',
          '#8fb98f',
        ],
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          6,
          3,
        ],
      },
    })
  }
  map.getSource<maplibregl.GeoJSONSource>(SOURCE)?.setData(tours)
  for (const f of tours.features) {
    map.setFeatureState(
      { source: SOURCE, id: f.properties.id },
      { selected: f.properties.id === selected },
    )
  }
}

function Stat({ icon: Icon, label }: { icon: LucideIcon; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-leaf-mint px-2 py-0.5 text-xs text-leaf-moss">
      <Icon aria-hidden className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

/** Vorgeschlagene Radtouren: four themed rides, each routed stop to stop, as cards next to a map. */
export default function SuggestedTours() {
  const { t } = useTranslation()
  const [tours, setTours] = useState<TourCollection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<TourId | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const toursRef = useRef<TourCollection | null>(null)
  const selectedRef = useRef<TourId | null>(null)
  toursRef.current = tours
  selectedRef.current = selected

  useEffect(() => {
    const controller = new AbortController()
    fetchTours(controller.signal)
      .then(setTours)
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message)
        }
      })
    return () => controller.abort()
  }, [])

  // mapRef is set on the first style load, so the map can take layers by then.
  useEffect(() => {
    if (mapRef.current && tours) {
      drawTours(mapRef.current, tours, selected)
    }
  }, [tours, selected])

  // Start and finish of the selected tour; a loop gets one marker for both.
  useEffect(() => {
    const map = mapRef.current
    const tour = tours?.features.find(f => f.properties.id === selected)
    if (!map || !tour) {
      return
    }
    const line = tour.geometry.coordinates
    const markers = tour.properties.loop
      ? [endMarker(line[0], t('greenest.highlights.tourStartEnd'), true)]
      : [
          endMarker(
            line[line.length - 1],
            t('greenest.highlights.tourEnd'),
            false,
          ),
          endMarker(line[0], t('greenest.highlights.tourStart'), true),
        ]
    markers.forEach(m => m.addTo(map))
    return () => markers.forEach(m => m.remove())
  }, [tours, selected, t])

  const select = (tour: Tour) => {
    setSelected(tour.properties.id)
    mapRef.current?.fitBounds(bounds(tour), { padding: 50, maxZoom: 15 })
  }

  // Called after every style load: draws the tours loaded so far (the effect above draws later ones).
  const onMapLoad = useCallback((map: maplibregl.Map) => {
    mapRef.current = map
    drawTours(map, toursRef.current ?? EMPTY, selectedRef.current)
    if (map.getLayer(`${SOURCE}-click`)) {
      return
    }
    // Wider invisible line, so a tour is easy to tap.
    map.addLayer({
      id: `${SOURCE}-click`,
      type: 'line',
      source: SOURCE,
      paint: { 'line-color': '#000000', 'line-opacity': 0, 'line-width': 18 },
    })
    map.on('click', `${SOURCE}-click`, e => {
      const id = e.features?.[0]?.properties?.id as TourId | undefined
      if (id) {
        setSelected(id)
        document
          .getElementById(`tour-${id}`)
          ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
      }
    })
    map.on('mouseenter', `${SOURCE}-click`, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', `${SOURCE}-click`, () => {
      map.getCanvas().style.cursor = ''
    })
  }, [])

  if (error) {
    return (
      <Card className="flex flex-col items-start gap-2 bg-leaf-cream md:flex-row md:items-center">
        <AvailabilityBadge availability="unavailable" />
        <p className="text-sm text-leaf-muted">
          {t('greenest.highlights.toursError', { error })}
        </p>
      </Card>
    )
  }

  const byId = new Map(
    (tours?.features ?? []).map(f => [f.properties.id, f as Tour]),
  )

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <ul aria-busy={!tours} className="grid gap-3 xs:grid-cols-2">
        {EXPERIENCES.map(id => {
          const Icon = TOUR_ICONS[id]
          const tour = byId.get(id)
          const p = tour?.properties
          const active = id === selected
          const title = t(`greenest.highlights.experiences.${id}.title`)
          return (
            <li id={`tour-${id}`} key={id}>
              <Card
                className={cx(
                  'flex h-full flex-col gap-3 transition-shadow',
                  active && 'ring-2 ring-leaf-fern',
                )}
              >
                <button
                  aria-pressed={active}
                  className="group flex flex-col gap-3 text-left disabled:cursor-wait"
                  disabled={!tour}
                  onClick={() => tour && select(tour)}
                  title={t('greenest.highlights.showOnMap')}
                  type="button"
                >
                  <span
                    className={cx(
                      'flex h-11 w-11 items-center justify-center rounded-full transition-colors',
                      active
                        ? 'bg-leaf-forest text-leaf-cream'
                        : 'bg-leaf-mint text-leaf-moss group-hover:bg-leaf-forest group-hover:text-leaf-cream',
                    )}
                  >
                    <Icon aria-hidden className="h-5 w-5" />
                  </span>
                  <h3 className="font-display text-lg font-medium text-leaf-forest group-hover:underline">
                    {title}
                  </h3>
                  <p className="text-sm text-leaf-muted">
                    {t(`greenest.highlights.experiences.${id}.text`)}
                  </p>
                </button>
                {p ? (
                  <div className="flex flex-wrap gap-1.5">
                    <Stat
                      icon={Route}
                      label={t('greenest.highlights.tourLength', {
                        km: (p.length_m / 1000).toFixed(1),
                      })}
                    />
                    <Stat
                      icon={Clock}
                      label={t('greenest.highlights.tourDuration', {
                        min: Math.round(p.duration_s / 60),
                      })}
                    />
                    <Stat
                      icon={Mountain}
                      label={t('greenest.highlights.tourClimb', {
                        m: Math.round(p.climb_m),
                      })}
                    />
                    <Stat
                      icon={Trees}
                      label={t('greenest.highlights.treeCover', {
                        share: percent(p.tree_share),
                      })}
                    />
                    <Stat
                      icon={Bike}
                      label={t('greenest.highlights.bikePaths', {
                        share: percent(p.bike_friendly_share),
                      })}
                    />
                    {p.loop && (
                      <Stat
                        icon={Repeat}
                        label={t('greenest.highlights.tourLoop')}
                      />
                    )}
                  </div>
                ) : (
                  <div className="h-12 animate-pulse rounded-2xl bg-leaf-cream" />
                )}
                {tour && active && (
                  <div className="flex flex-col gap-3 border-t border-leaf-sand pt-3">
                    <p className="text-xs leading-relaxed text-leaf-muted">
                      <span className="font-semibold text-leaf-moss">
                        {t('greenest.highlights.tourStops')}:{' '}
                      </span>
                      {tour.properties.stops.map(s => s.name).join(' → ')}
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-2">
                      <Link
                        className="flex items-center gap-1.5 text-sm font-medium text-leaf-moss hover:text-leaf-forest"
                        href={rideToStartHref(tour)}
                      >
                        <MapPin aria-hidden className="h-4 w-4" />
                        {t('greenest.highlights.rideToStart')}
                      </Link>
                      <button
                        className="flex items-center gap-1.5 text-sm font-medium text-leaf-moss hover:text-leaf-forest"
                        onClick={() => downloadGpx(tour, title)}
                        type="button"
                      >
                        <Download aria-hidden className="h-4 w-4" />
                        {t('greenest.highlights.downloadGpx')}
                      </button>
                    </div>
                  </div>
                )}
              </Card>
            </li>
          )
        })}
      </ul>
      <div className="h-80 overflow-hidden rounded-3xl ring-1 ring-leaf-sand lg:sticky lg:top-24 lg:h-[36rem]">
        <BaseMap
          ariaLabel={t('greenest.highlights.toursMapLabel')}
          onLoad={onMapLoad}
          zoom={12}
        />
      </div>
    </div>
  )
}
