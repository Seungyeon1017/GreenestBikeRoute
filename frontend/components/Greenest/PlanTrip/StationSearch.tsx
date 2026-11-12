'use client'

import { cx } from 'class-variance-authority'
import { TrainFront, X } from 'lucide-react'
import { useId, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type {
  TransitStopCollection,
  TransitStopProperties,
} from '@/types/greenest'
import { SBAHN_COLOR, stationKind, TRAIN_COLOR } from './transitLayers'

const MAX_MATCHES = 8

/** For name search: case, accents and umlauts don't matter (Sülmertor = sulmertor). */
function folded(text: string) {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** Stations whose name contains `query`; a word starting with it first, then by name. */
export function matchStations(
  stations: TransitStopProperties[],
  query: string,
): TransitStopProperties[] {
  const q = folded(query.trim())
  if (!q) {
    return []
  }
  const starts = (name: string) =>
    name.split(/[\s,/(-]+/).some(word => word.startsWith(q))
  return stations
    .map(s => ({ s, name: folded(s.name) }))
    .filter(({ name }) => name.includes(q))
    .sort(
      (a, b) =>
        Number(starts(b.name)) - Number(starts(a.name)) ||
        a.name.localeCompare(b.name),
    )
    .slice(0, MAX_MATCHES)
    .map(({ s }) => s)
}

/** The white S on a green disc, or the white train on a blue one, as on the map. */
export function StationBadge({ lines }: { lines: string[] }) {
  const sbahn = stationKind(lines) === 'sbahn'
  return (
    <span
      aria-hidden
      className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[12px] font-bold leading-none text-white"
      style={{ backgroundColor: sbahn ? SBAHN_COLOR : TRAIN_COLOR }}
    >
      {sbahn ? 'S' : <TrainFront className="h-3 w-3" strokeWidth={2.5} />}
    </span>
  )
}

type StationSearchProps = {
  label: string
  /** Every station of /transit/stops; null while they load. */
  stations: TransitStopCollection | null
  value: TransitStopProperties | null
  onChange: (_station: TransitStopProperties | null) => void
}

/** Search field over the timetable's stations (also outside Heilbronn), filtered as the rider types. */
export default function StationSearch({
  label,
  stations,
  value,
  onChange,
}: StationSearchProps) {
  const { t } = useTranslation()
  const s = (key: string) => t(`greenest.planTrip.train.station.${key}`)
  const id = useId()
  const listId = `${id}-list`
  const [text, setText] = useState('')
  const [typing, setTyping] = useState(false)
  const [active, setActive] = useState(-1)

  const all = useMemo(
    () => stations?.features.map(f => f.properties) ?? [],
    [stations],
  )
  const matches = useMemo(() => matchStations(all, text), [all, text])
  const open = typing && text.trim().length > 0

  function pick(station: TransitStopProperties) {
    setTyping(false)
    setText('')
    onChange(station)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'ArrowDown' && matches.length) {
      e.preventDefault()
      setActive(i => (i + 1) % matches.length)
    } else if (e.key === 'ArrowUp' && matches.length) {
      e.preventDefault()
      setActive(i => (i <= 0 ? matches.length - 1 : i - 1))
    } else if (e.key === 'Enter' && matches.length) {
      e.preventDefault()
      pick(matches[active >= 0 ? active : 0])
    } else if (e.key === 'Escape') {
      setTyping(false)
    }
  }

  return (
    <div className="relative flex flex-col gap-1 text-sm text-leaf-ink/80">
      <label htmlFor={id}>{label}</label>
      <div className="flex items-center gap-2 rounded-xl border border-leaf-sand bg-white px-3 py-2 focus-within:ring-2 focus-within:ring-leaf-moss">
        {value && !typing ? (
          <StationBadge lines={value.lines} />
        ) : (
          <TrainFront
            aria-hidden
            className="h-4 w-4 shrink-0 text-leaf-muted"
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
            setActive(-1)
            setText(e.target.value)
          }}
          onFocus={e => e.target.select()}
          onKeyDown={handleKeyDown}
          placeholder={s('placeholder')}
          role="combobox"
          type="text"
          value={typing ? text : (value?.name ?? '')}
        />
        {value && (
          <button
            aria-label={s('clear')}
            className="-my-1 -mr-1.5 rounded-lg p-1 text-leaf-muted hover:bg-leaf-cream"
            onClick={() => {
              setText('')
              onChange(null)
            }}
            title={s('clear')}
            type="button"
          >
            <X aria-hidden className="h-4 w-4" />
          </button>
        )}
      </div>

      {open && (
        <div className="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-xl border border-leaf-sand bg-white shadow-soft">
          {matches.length > 0 ? (
            <ul id={listId} role="listbox">
              {matches.map((station, i) => (
                <li
                  aria-selected={i === active}
                  className={cx(
                    'flex cursor-pointer items-center gap-2.5 px-3 py-2',
                    i === active ? 'bg-leaf-mint' : 'hover:bg-leaf-cream',
                  )}
                  id={`${listId}-${i}`}
                  key={station.stop_id}
                  // mousedown, not click: it fires before the input's blur.
                  onMouseDown={e => {
                    e.preventDefault()
                    pick(station)
                  }}
                  role="option"
                >
                  <StationBadge lines={station.lines} />
                  <span className="flex min-w-0 flex-col">
                    <span className="font-medium text-leaf-ink">
                      {station.name}
                    </span>
                    <span className="truncate text-xs text-leaf-muted">
                      {station.lines.join(' · ')}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-xs text-leaf-muted" role="status">
              {stations ? s('noMatch') : s('loading')}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
