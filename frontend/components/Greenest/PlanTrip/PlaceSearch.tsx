'use client'

import { cx } from 'class-variance-authority'
import { LocateFixed, MapPin, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchPlaces, fetchPlaceSuggestions } from '@/services/greenestApi'
import type {
  LngLat,
  PlaceCollection,
  TransitStopCollection,
  TransitStopFeature,
  TransitStopProperties,
} from '@/types/greenest'
import PlaceIcon from './PlaceIcon'
import {
  folded,
  matchStations,
  metresBetween,
  StationBadge,
  stationOfPlace,
} from './stations'

/** The place search (/geocode) answers 422 below this many characters. */
const MIN_CHARS = 3
/** Suggestions from the backend's own names (/geocode/suggest) start earlier: they are instant. */
const MIN_SUGGEST_CHARS = 2
// Nominatim asks not to search on every keystroke: wait for a pause in typing.
const DEBOUNCE_MS = 350
/** Station suggestions above the places, from the timetable (also outside Heilbronn). */
const MAX_STATIONS = 3
const MAX_PLACES = 6
/** Two places of one name this close are the same place, found twice. */
const SAME_PLACE_M = 400

/** What the place search answered, by query: typing a letter back, or the same place in the other field, asks nothing. */
const searched = new Map<string, PlaceCollection>()

type PlaceFeature = PlaceCollection['features'][number]

const point = (f: { geometry: { coordinates: number[] } }): LngLat => [
  f.geometry.coordinates[0],
  f.geometry.coordinates[1],
]
const nameOf = (f: PlaceFeature) =>
  f.properties.name ?? f.properties.label.split(',')[0]

type PlaceSearchProps = {
  label: string
  placeholder: string
  /** The text in the field: what the rider typed, a picked place, or a clicked point. */
  value: string
  onValueChange: (_value: string) => void
  onPick: (_point: LngLat, _label: string) => void
  /** Colour of the pin in front of the field (start green, destination red). */
  pinClassName?: string
  /** When set, a "use my location" button sits at the end of the field. */
  onLocate?: () => void
  /** The browser is still looking up the location: the button pulses and is disabled. */
  locating?: boolean
  /** Every train station: matching ones are suggested first; picking one calls onPickStation. */
  stations?: TransitStopCollection | null
  onPickStation?: (_station: TransitStopProperties, _point: LngLat) => void
  /** The field holds a picked station: its badge replaces the pin. */
  station?: TransitStopProperties | null
}

/**
 * Search field with a list like a map app's search box, filled from three sources as the
 * rider types: the train stations whose name matches (at once, they are loaded already),
 * names the backend completes itself (`/geocode/suggest`, at once: "Wests" → Weststraße) and,
 * after a pause in typing, the place search (`/geocode`, Nominatim: addresses and places not
 * searched before). A place that is a station is listed once, as the station. Only searches
 * after the rider typed (not when the field is filled by a pick or a map click).
 */
export default function PlaceSearch({
  label,
  placeholder,
  value,
  onValueChange,
  onPick,
  pinClassName,
  onLocate,
  locating = false,
  stations,
  onPickStation,
  station,
}: PlaceSearchProps) {
  const { t } = useTranslation()
  const id = useId()
  const listId = `${id}-list`

  // True after a keystroke, false once a place is picked: the list only shows while typing.
  const [typing, setTyping] = useState(false)
  // Completed names, there at once; kept while the next keystroke's are on their way.
  const [suggestions, setSuggestions] = useState<PlaceCollection | null>(null)
  const [places, setPlaces] = useState<PlaceCollection | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  // The place search takes a second or two: say it's still looking.
  const [searching, setSearching] = useState(false)
  const [active, setActive] = useState(-1)

  const query = value.trim()

  const { stationList, placeList, farStations } = useMemo(() => {
    const stationList: TransitStopFeature[] =
      typing && stations && onPickStation
        ? matchStations(stations.features, query, MAX_STATIONS)
        : []
    const placeList: PlaceFeature[] = []
    if (!typing) {
      return { stationList, placeList, farStations: [] }
    }
    // The completed names stay on top where the rider saw them; the place search adds below.
    for (const f of [
      ...(suggestions?.features ?? []),
      ...(places?.features ?? []),
    ]) {
      const asStation =
        stations && onPickStation
          ? stationOfPlace(stations.features, f.properties, point(f))
          : null
      if (asStation) {
        if (!stationList.includes(asStation)) {
          stationList.push(asStation)
        }
        continue
      }
      const twin = placeList.findIndex(
        p =>
          folded(nameOf(p)) === folded(nameOf(f)) &&
          metresBetween(point(p), point(f)) <= SAME_PLACE_M,
      )
      if (twin < 0) {
        placeList.push(f)
      } else if (placeList[twin].properties.local && !f.properties.local) {
        // The place search knows the district: its label replaces the bare street name.
        placeList[twin] = f
      }
    }
    // Heilbronn first: its stations, then its places. A station elsewhere that only has the
    // typed letters somewhere in its name ("Wests" in "Heidelberg, Weststadt") comes last;
    // one whose name starts with them ("Mosb") is what the rider is after and stays on top.
    const q = folded(query)
    const top = (s: TransitStopFeature) =>
      s.properties.rideable !== false || folded(s.properties.name).startsWith(q)
    return {
      stationList: stationList.filter(top),
      placeList: placeList.slice(0, MAX_PLACES),
      farStations: stationList.filter(s => !top(s)),
    }
  }, [typing, stations, onPickStation, query, suggestions, places])

  // One list for the arrow keys: the stations, the places, then the stations elsewhere.
  const count = stationList.length + placeList.length + farStations.length
  const open = typing && (count > 0 || message !== null || searching)
  // "No place found" next to a list of matches would read as if nothing was found.
  const showMessage = message !== null && count === 0

  // Names the backend completes itself: asked on every keystroke.
  useEffect(() => {
    if (!typing || query.length < MIN_SUGGEST_CHARS) {
      setSuggestions(null)
      return
    }
    const controller = new AbortController()
    fetchPlaceSuggestions(query, controller.signal)
      .then(data => {
        setSuggestions(data)
        setActive(-1)
      })
      // Without them the stations and the place search still fill the list.
      .catch(() => undefined)
    return () => controller.abort()
  }, [typing, query])

  // The place search: after a pause in typing, unless this query was answered before.
  useEffect(() => {
    // A new query: the places of the last one no longer apply.
    setMessage(null)
    if (!typing || query.length < MIN_CHARS) {
      setPlaces(null)
      setSearching(false)
      return
    }
    const key = folded(query)
    const show = (data: PlaceCollection) => {
      setSearching(false)
      setPlaces(data)
      setMessage(
        data.features.length ? null : t('greenest.planTrip.search.noMatch'),
      )
    }
    const known = searched.get(key)
    if (known) {
      show(known)
      return
    }
    setPlaces(null)
    setSearching(true)
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetchPlaces(query, controller.signal)
        .then(data => {
          searched.set(key, data)
          show(data)
        })
        .catch(err => {
          if (err.name === 'AbortError') {
            return
          }
          setSearching(false)
          setPlaces(null)
          setMessage(
            err.status === 503
              ? t('greenest.planTrip.search.unavailable')
              : err.message,
          )
        })
    }, DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [typing, query, t])

  function pick(index: number) {
    const hit =
      stationList[index] ??
      farStations[index - stationList.length - placeList.length]
    if (hit) {
      setTyping(false)
      onPickStation?.(hit.properties, point(hit))
      return
    }
    const feature = placeList[index - stationList.length]
    if (!feature) {
      return
    }
    setTyping(false)
    onPick(point(feature), nameOf(feature))
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' && count) {
      e.preventDefault()
      setActive(i => (i + 1) % count)
    } else if (e.key === 'ArrowUp' && count) {
      e.preventDefault()
      setActive(i => (i <= 0 ? count - 1 : i - 1))
    } else if (e.key === 'Enter' && count) {
      e.preventDefault()
      pick(active >= 0 && active < count ? active : 0)
    } else if (e.key === 'Escape') {
      setTyping(false)
    }
  }

  const stationRow = (f: TransitStopFeature, i: number) => (
    <li
      aria-selected={i === active}
      className={cx(
        'flex cursor-pointer items-center gap-2.5 px-3 py-2',
        i === active ? 'bg-leaf-mint' : 'hover:bg-leaf-cream',
      )}
      id={`${listId}-${i}`}
      key={f.properties.stop_id}
      onMouseDown={e => {
        e.preventDefault()
        pick(i)
      }}
      role="option"
    >
      <StationBadge lines={f.properties.lines} />
      <span className="flex min-w-0 flex-col">
        <span className="font-medium text-leaf-ink">{f.properties.name}</span>
        <span className="truncate text-xs text-leaf-muted">
          {f.properties.rideable === false
            ? t('greenest.planTrip.search.stationOutside', {
                lines: f.properties.lines.join(' · '),
              })
            : t('greenest.planTrip.search.station', {
                lines: f.properties.lines.join(' · '),
              })}
        </span>
      </span>
    </li>
  )

  return (
    <div className="relative flex flex-col gap-1 text-sm text-leaf-ink/80">
      <label htmlFor={id}>{label}</label>
      <div className="flex items-center gap-2 rounded-xl border border-leaf-sand bg-white px-3 py-2 focus-within:ring-2 focus-within:ring-leaf-moss">
        {station && !typing ? (
          <StationBadge lines={station.lines} />
        ) : (
          <MapPin
            aria-hidden
            className={cx('h-4 w-4 shrink-0', pinClassName)}
          />
        )}
        <input
          aria-activedescendant={
            open && active >= 0 ? `${listId}-${active}` : undefined
          }
          aria-autocomplete="list"
          aria-controls={listId}
          aria-expanded={open}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-leaf-muted/70"
          id={id}
          // Let a click on a suggestion land before the list closes.
          onBlur={() => setTimeout(() => setTyping(false), 150)}
          onChange={e => {
            setTyping(true)
            onValueChange(e.target.value)
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          role="combobox"
          type="text"
          value={value}
        />
        <Search aria-hidden className="h-4 w-4 shrink-0 text-leaf-muted" />
        {onLocate && (
          <button
            aria-label={t('greenest.planTrip.locate.button')}
            className="-my-1 -mr-1.5 rounded-lg p-1 text-leaf-forest hover:bg-leaf-cream disabled:cursor-wait"
            disabled={locating}
            onClick={onLocate}
            title={t('greenest.planTrip.locate.button')}
            type="button"
          >
            <LocateFixed
              aria-hidden
              className={cx('h-4 w-4', locating && 'animate-pulse')}
            />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-leaf-sand bg-white shadow-soft">
          {count > 0 && (
            <ul id={listId} role="listbox">
              {stationList.map((f, i) => stationRow(f, i))}
              {placeList.map((f, j) => {
                const i = stationList.length + j
                return (
                  <li
                    aria-selected={i === active}
                    className={cx(
                      'flex cursor-pointer items-center gap-2.5 px-3 py-2',
                      i === active ? 'bg-leaf-mint' : 'hover:bg-leaf-cream',
                    )}
                    id={`${listId}-${i}`}
                    key={`${f.properties.label}-${j}`}
                    // mousedown, not click: it fires before the input's blur.
                    onMouseDown={e => {
                      e.preventDefault()
                      pick(i)
                    }}
                    role="option"
                  >
                    <PlaceIcon
                      category={f.properties.category}
                      type={f.properties.type}
                    />
                    <span className="flex min-w-0 flex-col">
                      <span className="font-medium text-leaf-ink">
                        {nameOf(f)}
                      </span>
                      <span className="truncate text-xs text-leaf-muted">
                        {f.properties.local
                          ? t('greenest.planTrip.search.localStreet')
                          : f.properties.label}
                      </span>
                    </span>
                  </li>
                )
              })}
              {farStations.map((f, j) =>
                stationRow(f, stationList.length + placeList.length + j),
              )}
            </ul>
          )}
          {searching && (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {t(
                count > 0
                  ? 'greenest.planTrip.search.searchingMore'
                  : 'greenest.planTrip.search.searching',
              )}
            </p>
          )}
          {showMessage && (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {message}
            </p>
          )}
          {placeList.length > 0 && (
            <p className="border-t border-leaf-sand/70 px-3 py-1.5 text-[11px] text-leaf-muted">
              {(places ?? suggestions)?.attribution}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
