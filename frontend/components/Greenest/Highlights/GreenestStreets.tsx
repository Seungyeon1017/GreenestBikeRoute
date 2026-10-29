'use client'

import { cx } from 'class-variance-authority'
import type { Feature, MultiLineString } from 'geojson'
import { Bike, MapPin, Route, Trees, Wind } from 'lucide-react'
import maplibregl from 'maplibre-gl'
import Link from 'next/link'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card from '@/components/Greenest/ui/Card'
import { fetchGreenestStreets } from '@/services/greenestApi'
import type {
  GreenStreetCollection,
  GreenStreetProperties,
  LngLat,
} from '@/types/greenest'

type GreenStreet = Feature<MultiLineString, GreenStreetProperties>

/** How many streets the list shows first, and after "Show more". */
const FEW = 10
const MORE = 25

const SOURCE = 'green-streets'
const EMPTY: GreenStreetCollection = {
  type: 'FeatureCollection',
  features: [],
  total: 0,
}

/** Air score (0.5 = usual): a little either way is still usual, as streets agree only weakly between bikes. */
function airKey(pmRisk: number) {
  if (pmRisk < 0.49) {
    return 'cleaner'
  }
  return pmRisk > 0.51 ? 'worse' : 'usual'
}

function percent(share: number) {
  return `${Math.round(share * 100)} %`
}

/** Middle point of the street's longest ridden stretch, as the trip destination. */
function middle(street: GreenStreet): LngLat {
  const longest = street.geometry.coordinates.reduce((a, b) =>
    b.length > a.length ? b : a,
  )
  const [lng, lat] = longest[Math.floor(longest.length / 2)]
  return [lng, lat]
}

/** Plan trip reads `to` (lng,lat) and `name` and sets that place as the destination. */
function planTripHref(street: GreenStreet) {
  const [lng, lat] = middle(street)
  const query = new URLSearchParams({
    to: `${lng},${lat}`,
    name: street.properties.name,
  })
  return `/plan-trip?${query}`
}

function bounds(street: GreenStreet) {
  const all = street.geometry.coordinates.flat() as LngLat[]
  return all.reduce(
    (b, point) => b.extend(point),
    new maplibregl.LngLatBounds(all[0], all[0]),
  )
}

/** Adds the street layers the first time (and after a style reload), then puts the streets into them. */
function drawStreets(map: maplibregl.Map, streets: GreenStreetCollection) {
  if (!map.getSource(SOURCE)) {
    map.addSource(SOURCE, {
      type: 'geojson',
      data: EMPTY,
      promoteId: 'rank',
    })
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
          7,
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
          '#5f8f63',
        ],
        'line-width': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          7,
          4,
        ],
      },
    })
  }
  map.getSource<maplibregl.GeoJSONSource>(SOURCE)?.setData(streets)
}

function Stat({ icon: Icon, label }: { icon: typeof Trees; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-leaf-mint px-2 py-0.5 text-xs text-leaf-moss">
      <Icon aria-hidden className="h-3.5 w-3.5" />
      {label}
    </span>
  )
}

/** Grünste Straßen: the greenest streets bikes have ridden, as a ranked list next to a map. */
export default function GreenestStreets() {
  const { t } = useTranslation()
  const [limit, setLimit] = useState(FEW)
  const [streets, setStreets] = useState<GreenStreetCollection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const selectedRef = useRef<number | null>(null)
  const streetsRef = useRef<GreenStreetCollection | null>(null)
  streetsRef.current = streets

  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    fetchGreenestStreets(limit, controller.signal)
      .then(setStreets)
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message)
        }
      })
    return () => controller.abort()
  }, [limit])

  // mapRef is set on the first style load, so the map can take layers by then.
  useEffect(() => {
    if (mapRef.current && streets) {
      drawStreets(mapRef.current, streets)
    }
  }, [streets])

  // Keep the map's highlight on the selected street.
  useEffect(() => {
    const map = mapRef.current
    const previous = selectedRef.current
    selectedRef.current = selected
    if (!map?.getSource(SOURCE)) {
      return
    }
    if (previous !== null) {
      map.setFeatureState({ source: SOURCE, id: previous }, { selected: false })
    }
    if (selected !== null) {
      map.setFeatureState({ source: SOURCE, id: selected }, { selected: true })
    }
  }, [selected])

  const select = (street: GreenStreet) => {
    setSelected(street.properties.rank)
    mapRef.current?.fitBounds(bounds(street), { padding: 60, maxZoom: 16 })
  }

  // Called after every style load: draws the streets loaded so far (the effect above draws later ones).
  const onMapLoad = useCallback((map: maplibregl.Map) => {
    mapRef.current = map
    drawStreets(map, streetsRef.current ?? EMPTY)
    if (selectedRef.current !== null) {
      map.setFeatureState(
        { source: SOURCE, id: selectedRef.current },
        { selected: true },
      )
    }
    if (map.getLayer(`${SOURCE}-click`)) {
      return
    }
    // Wider invisible line, so a thin street is easy to tap.
    map.addLayer({
      id: `${SOURCE}-click`,
      type: 'line',
      source: SOURCE,
      paint: { 'line-color': '#000000', 'line-opacity': 0, 'line-width': 18 },
    })
    map.on('click', `${SOURCE}-click`, e => {
      const rank = e.features?.[0]?.properties?.rank
      if (typeof rank === 'number') {
        setSelected(rank)
        document
          .getElementById(`green-street-${rank}`)
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
          {t('greenest.highlights.roadsError', { error })}
        </p>
      </Card>
    )
  }

  const features = (streets?.features ?? []) as GreenStreet[]

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <Card className="flex flex-col gap-3 p-3 md:p-4">
        <div className="flex flex-wrap items-center gap-2 px-1">
          <AvailabilityBadge availability="measured" />
          <p className="text-xs text-leaf-muted">
            {streets
              ? t('greenest.highlights.roadsQualified', {
                  count: streets.total,
                })
              : t('greenest.highlights.roadsLoading')}
          </p>
        </div>
        <ol aria-busy={!streets} className="flex flex-col gap-2">
          {!streets &&
            Array.from({ length: 5 }, (_, i) => (
              <li
                className="h-24 animate-pulse rounded-2xl bg-leaf-cream"
                key={i}
              />
            ))}
          {features.map(street => {
            const p = street.properties
            const active = p.rank === selected
            return (
              <li id={`green-street-${p.rank}`} key={p.rank}>
                <div
                  className={cx(
                    'flex gap-3 rounded-2xl border p-3 transition-colors',
                    active
                      ? 'border-leaf-fern bg-leaf-mint/60'
                      : 'border-transparent bg-leaf-cream/60 hover:border-leaf-sand',
                  )}
                >
                  <span
                    className={cx(
                      'flex h-9 w-9 shrink-0 items-center justify-center rounded-full font-display text-base font-semibold',
                      p.rank <= 3
                        ? 'bg-leaf-forest text-leaf-cream'
                        : 'bg-white text-leaf-forest ring-1 ring-leaf-sand',
                    )}
                  >
                    {p.rank}
                  </span>
                  <div className="flex min-w-0 flex-1 flex-col gap-2">
                    <button
                      aria-pressed={active}
                      className="flex items-baseline justify-between gap-2 text-left"
                      onClick={() => select(street)}
                      title={t('greenest.highlights.showOnMap')}
                      type="button"
                    >
                      <h3 className="truncate font-display text-lg font-medium text-leaf-forest hover:underline">
                        {p.name}
                      </h3>
                      <span className="shrink-0 text-sm font-semibold text-leaf-moss">
                        {t('greenest.highlights.greenScore', {
                          score: Math.round(p.green_score),
                        })}
                      </span>
                    </button>
                    <div
                      aria-hidden
                      className="h-1.5 overflow-hidden rounded-full bg-leaf-sand/70"
                    >
                      <div
                        className="h-full rounded-full bg-leaf-fern"
                        style={{ width: `${p.green_score}%` }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      <Stat
                        icon={Trees}
                        label={t('greenest.highlights.treeCover', {
                          share: percent(p.tree_cover),
                        })}
                      />
                      <Stat
                        icon={Bike}
                        label={t('greenest.highlights.bikePaths', {
                          share: percent(p.bike_friendly_share),
                        })}
                      />
                      <Stat
                        icon={Wind}
                        label={t(
                          `greenest.highlights.air.${airKey(p.pm_risk)}`,
                        )}
                      />
                      <Stat
                        icon={Route}
                        label={t('greenest.highlights.ridden', {
                          km: (p.ridden_m / 1000).toFixed(1),
                        })}
                      />
                    </div>
                    <Link
                      className="flex items-center gap-1.5 self-start text-sm font-medium text-leaf-moss hover:text-leaf-forest"
                      href={planTripHref(street)}
                    >
                      <MapPin aria-hidden className="h-4 w-4" />
                      {t('greenest.highlights.rideThere')}
                    </Link>
                  </div>
                </div>
              </li>
            )
          })}
        </ol>
        {streets && streets.total > limit && limit < MORE && (
          <button
            className="self-center rounded-full border border-leaf-sand px-4 py-2 text-sm font-medium text-leaf-moss hover:bg-leaf-mint"
            onClick={() => setLimit(MORE)}
            type="button"
          >
            {t('greenest.highlights.showMore', { count: MORE })}
          </button>
        )}
        <p className="px-1 text-xs leading-relaxed text-leaf-muted">
          {t('greenest.highlights.roadsMethod')}
        </p>
      </Card>
      <div className="h-80 overflow-hidden rounded-3xl ring-1 ring-leaf-sand lg:sticky lg:top-24 lg:h-[36rem]">
        <BaseMap
          ariaLabel={t('greenest.highlights.roadsMapLabel')}
          onLoad={onMapLoad}
          zoom={12}
        />
      </div>
    </div>
  )
}
