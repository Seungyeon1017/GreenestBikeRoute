'use client'

import { cx } from 'class-variance-authority'
import { Moon, Pause, Play, Sun } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { DayPeriod, DayRoutes } from '@/types/greenest'

/** How long the play button stays on each stop. */
const PLAY_STEP_MS = 1500

/**
 * One choice on the day slider: a shade slot of the backend ("09:00", "12:00", …)
 * or the night. The backend only has shade for these slots, so the route can only
 * change between them and at dusk and dawn.
 */
export type DayStop = {
  /** "HH:MM" of the shade slot, or "night". */
  key: string
  /** Departure for the hills and the rented-vehicle trip at this stop: the slot itself, or the evening's dark. */
  departAt: string
  /** The departures ("HH:MM", end excluded) this stop covers; the night has one before dawn and one after dusk. */
  ranges: Array<{ from: string; to: string }>
  period: DayPeriod
}

/** The day's periods as stops: the shade slots in order, then the night. */
export function dayStops(day: DayRoutes): DayStop[] {
  const slots: DayStop[] = []
  let night: DayStop | null = null
  for (const p of day.periods) {
    const range = { from: p.from, to: p.to }
    const slot = p.route.properties.daylight
      ? p.route.properties.shade_slot?.slice(11, 16)
      : null
    if (slot) {
      slots.push({ key: slot, departAt: slot, ranges: [range], period: p })
    } else if (night) {
      // The evening's dark: when people ride home, rather than 00:00.
      night.ranges.push(range)
      night.departAt = p.from
    } else {
      night = { key: 'night', departAt: p.from, ranges: [range], period: p }
    }
  }
  return night ? [...slots, night] : slots
}

/** The stop whose departures include `time` ("HH:MM"). */
export function stopAt(stops: DayStop[], time: string): number {
  return Math.max(
    0,
    stops.findIndex(s => s.ranges.some(r => time >= r.from && time < r.to)),
  )
}

type DaySliderProps = {
  stops: DayStop[]
  index: number
  onIndexChange: (_index: number) => void
}

/** Buttons for the times of day with their own route, and a play button that steps through them. */
export default function DaySlider({
  stops,
  index,
  onIndexChange,
}: DaySliderProps) {
  const { t } = useTranslation()
  const [playing, setPlaying] = useState(false)
  // The interval reads the latest stop without restarting on each step.
  const indexRef = useRef(index)
  indexRef.current = index

  useEffect(() => {
    if (!playing || stops.length < 2) {
      return
    }
    const timer = setInterval(
      () => onIndexChange((indexRef.current + 1) % stops.length),
      PLAY_STEP_MS,
    )
    return () => clearInterval(timer)
  }, [playing, stops.length, onIndexChange])

  if (!stops.length) {
    return null
  }
  const stop = stops[index]
  const ranges = stop.ranges
    .map(r => t('greenest.planTrip.day.range', r))
    .join(', ')

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-1.5">
        <button
          aria-label={
            playing
              ? t('greenest.planTrip.day.pause')
              : t('greenest.planTrip.day.play')
          }
          className="rounded-full border border-leaf-sand p-1.5 text-leaf-ink hover:bg-leaf-cream disabled:opacity-40"
          disabled={stops.length < 2}
          onClick={() => setPlaying(p => !p)}
          type="button"
        >
          {playing ? (
            <Pause aria-hidden className="h-3.5 w-3.5" />
          ) : (
            <Play aria-hidden className="h-3.5 w-3.5" />
          )}
        </button>
        <div
          aria-label={t('greenest.planTrip.day.label')}
          className="flex flex-1 overflow-hidden rounded-lg border border-leaf-sand"
          role="radiogroup"
        >
          {stops.map((s, i) => (
            <button
              aria-checked={i === index}
              className={cx(
                'flex flex-1 items-center justify-center gap-1 border-l border-leaf-sand px-1 py-1 text-xs tabular-nums first:border-l-0',
                i === index
                  ? 'bg-leaf-forest font-semibold text-white'
                  : 'bg-white text-leaf-ink hover:bg-leaf-cream',
              )}
              key={s.key}
              onClick={() => {
                setPlaying(false)
                onIndexChange(i)
              }}
              role="radio"
              title={
                s.key === 'night' ? t('greenest.planTrip.day.night') : undefined
              }
              type="button"
            >
              {/* The night as a moon only: a fifth time label doesn't fit beside four. */}
              {s.key === 'night' ? (
                <>
                  <Moon aria-hidden className="h-3.5 w-3.5" />
                  <span className="sr-only">
                    {t('greenest.planTrip.day.night')}
                  </span>
                </>
              ) : (
                <>
                  <Sun aria-hidden className="h-3 w-3" />
                  {s.key}
                </>
              )}
            </button>
          ))}
        </div>
      </div>
      <span className="text-xs text-leaf-muted">
        {t('greenest.planTrip.day.departures', { ranges })}
      </span>
    </div>
  )
}
