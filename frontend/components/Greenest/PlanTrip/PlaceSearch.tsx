'use client'

import { cx } from 'class-variance-authority'
import { LocateFixed, MapPin, Search } from 'lucide-react'
import { useEffect, useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchPlaces } from '@/services/greenestApi'
import type {
  LngLat,
  PlaceCollection,
  TransitStopCollection,
  TransitStopProperties,
} from '@/types/greenest'
import PlaceIcon from './PlaceIcon'
import { matchStations, StationBadge } from './stations'

/** The backend answers 422 below this many characters. */
const MIN_CHARS = 3
const DEBOUNCE_MS = 400
/** Station suggestions above the places, from the timetable (also outside Heilbronn). */
const MAX_STATIONS = 3

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
 * Search field with a "did you mean" list from `/geocode`, like a map app's search box, and the
 * train stations whose name matches on top. Only searches after the rider typed (not when the
 * field is filled by a pick or a map click).
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
  const [places, setPlaces] = useState<PlaceCollection | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  // The place search is slow (Nominatim, up to ~10 s) while stations match at once: say it's still looking.
  const [searching, setSearching] = useState(false)
  const [active, setActive] = useState(-1)

  const query = value.trim()
  const stationMatches = useMemo(
    () =>
      typing && stations && onPickStation
        ? matchStations(stations.features, query, MAX_STATIONS)
        : [],
    [typing, stations, onPickStation, query],
  )
  const placeCount = places?.features.length ?? 0
  // One list for the arrow keys: the stations, then the places.
  const count = stationMatches.length + placeCount
  const open =
    typing &&
    (stationMatches.length > 0 ||
      places !== null ||
      message !== null ||
      searching)
  // "No place found" next to matching stations would read as if nothing was found.
  const noMatch = t('greenest.planTrip.search.noMatch')
  const showMessage =
    message !== null && !(stationMatches.length > 0 && message === noMatch)

  useEffect(() => {
    // A new query: the places of the last one no longer apply.
    setPlaces(null)
    setMessage(null)
    if (!typing || query.length < MIN_CHARS) {
      setSearching(false)
      return
    }
    setSearching(true)
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetchPlaces(query, controller.signal)
        .then(data => {
          setSearching(false)
          setPlaces(data)
          setActive(-1)
          setMessage(
            data.features.length ? null : t('greenest.planTrip.search.noMatch'),
          )
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
    const hit = stationMatches[index]
    if (hit) {
      const [lng, lat] = hit.geometry.coordinates
      setTyping(false)
      onPickStation?.(hit.properties, [lng, lat])
      return
    }
    const feature = places?.features[index - stationMatches.length]
    if (!feature) {
      return
    }
    const { name, label: fullLabel } = feature.properties
    const [lng, lat] = feature.geometry.coordinates
    setTyping(false)
    onPick([lng, lat], name ?? fullLabel)
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
      pick(active >= 0 ? active : 0)
    } else if (e.key === 'Escape') {
      setTyping(false)
    }
  }

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
              {stationMatches.map((f, i) => (
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
                    <span className="font-medium text-leaf-ink">
                      {f.properties.name}
                    </span>
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
              ))}
              {places?.features.map((f, j) => {
                const i = stationMatches.length + j
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
                        {f.properties.name ?? f.properties.label.split(',')[0]}
                      </span>
                      <span className="truncate text-xs text-leaf-muted">
                        {f.properties.label}
                      </span>
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
          {searching && (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {t('greenest.planTrip.search.searching')}
            </p>
          )}
          {showMessage && (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {message}
            </p>
          )}
          {places && placeCount > 0 && (
            <p className="border-t border-leaf-sand/70 px-3 py-1.5 text-[11px] text-leaf-muted">
              {places.attribution}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
