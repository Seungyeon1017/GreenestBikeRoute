'use client'

import { cx } from 'class-variance-authority'
import { MapPin, Search } from 'lucide-react'
import { useEffect, useId, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchPlaces } from '@/services/greenestApi'
import type { LngLat, PlaceCollection } from '@/types/greenest'

/** The backend answers 422 below this many characters. */
const MIN_CHARS = 3
const DEBOUNCE_MS = 400

type PlaceSearchProps = {
  label: string
  placeholder: string
  /** The text in the field: what the rider typed, a picked place, or a clicked point. */
  value: string
  onValueChange: (_value: string) => void
  onPick: (_point: LngLat, _label: string) => void
  /** Colour of the pin in front of the field (start green, destination red). */
  pinClassName?: string
}

/**
 * Search field with a "did you mean" list from `/geocode`, like a map app's search box.
 * Only searches after the rider typed (not when the field is filled by a pick or a map click).
 */
export default function PlaceSearch({
  label,
  placeholder,
  value,
  onValueChange,
  onPick,
  pinClassName,
}: PlaceSearchProps) {
  const { t } = useTranslation()
  const id = useId()
  const listId = `${id}-list`

  // True after a keystroke, false once a place is picked: the list only shows while typing.
  const [typing, setTyping] = useState(false)
  const [places, setPlaces] = useState<PlaceCollection | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [active, setActive] = useState(-1)

  const query = value.trim()
  const open = typing && (places !== null || message !== null)

  useEffect(() => {
    if (!typing || query.length < MIN_CHARS) {
      setPlaces(null)
      setMessage(null)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetchPlaces(query, controller.signal)
        .then(data => {
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
    const feature = places?.features[index]
    if (!feature) {
      return
    }
    const { name, label: fullLabel } = feature.properties
    const [lng, lat] = feature.geometry.coordinates
    setTyping(false)
    onPick([lng, lat], name ?? fullLabel)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    const count = places?.features.length ?? 0
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
        <MapPin aria-hidden className={cx('h-4 w-4 shrink-0', pinClassName)} />
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
      </div>

      {open && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-leaf-sand bg-white shadow-soft">
          {places && places.features.length > 0 && (
            <ul id={listId} role="listbox">
              {places.features.map((f, i) => (
                <li
                  aria-selected={i === active}
                  className={cx(
                    'flex cursor-pointer flex-col px-3 py-2',
                    i === active ? 'bg-leaf-mint' : 'hover:bg-leaf-cream',
                  )}
                  id={`${listId}-${i}`}
                  key={`${f.properties.label}-${i}`}
                  // mousedown, not click: it fires before the input's blur.
                  onMouseDown={e => {
                    e.preventDefault()
                    pick(i)
                  }}
                  role="option"
                >
                  <span className="font-medium text-leaf-ink">
                    {f.properties.name ?? f.properties.label.split(',')[0]}
                  </span>
                  <span className="truncate text-xs text-leaf-muted">
                    {f.properties.label}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {message && (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {message}
            </p>
          )}
          {places && places.features.length > 0 && (
            <p className="border-t border-leaf-sand/70 px-3 py-1.5 text-[11px] text-leaf-muted">
              {places.attribution}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
