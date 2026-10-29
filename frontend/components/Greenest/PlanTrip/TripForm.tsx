'use client'

import { cx } from 'class-variance-authority'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { LngLat, RouteOptions } from '@/types/greenest'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import { isSunUp } from '@/lib/sun'
import PlaceSearch from './PlaceSearch'

type TripFormProps = {
  /** Text in the Start and Destination fields. */
  startLabel: string
  endLabel: string
  onStartLabelChange: (_label: string) => void
  onEndLabelChange: (_label: string) => void
  /** A place was picked from the search list. */
  onPickStart: (_point: LngLat, _label: string) => void
  onPickEnd: (_point: LngLat, _label: string) => void
  options: RouteOptions
  onOptionsChange: (_options: RouteOptions) => void
  onReset: () => void
  /** "Through the day": the route for each time of day instead of one departure. */
  dayMode: boolean
  onDayModeChange: (_on: boolean) => void
  /** The day slider, shown in place of the departure hint while dayMode is on. */
  daySlider?: ReactNode
  loading?: boolean
}

/** The options that are numbers, i.e. the ones shown as sliders. */
type SliderKey =
  | 'bump'
  | 'danger'
  | 'pm'
  | 'stop'
  | 'bikeFriendly'
  | 'shade'
  | 'dark'

type SliderSpec = { key: SliderKey; min: number; max: number; step: number }

/**
 * The backend counts the dislikes in whole points 0–10, each making a bad street
 * cost 25 % more (routing/costs.py, MAX_POINTS); close overtaking is metres of detour.
 */
const MAX_POINTS = 10
const points = (key: SliderKey): SliderSpec => ({
  key,
  min: 0,
  max: MAX_POINTS,
  step: 1,
})

/** Under "Options", always usable. Min, max and step match the backend limits. */
const OPTION_SLIDERS: SliderSpec[] = [
  points('bump'),
  { key: 'danger', min: 0, max: 100, step: 1 },
  points('pm'),
  points('stop'),
  points('bikeFriendly'),
]

/** Only used by the backend when a departure time is set: shade by day, lighting after dark. */
const TIME_SLIDERS: SliderSpec[] = [points('shade'), points('dark')]

/** Share each dislike point adds on a bad street (routing/costs.py, POINT). */
const POINT = 0.25

/** Rows of the info panel: 0, 4 (twice as long) and the maximum, plus the rider's own value. */
const POINT_ROWS = [0, 4, MAX_POINTS]
const DANGER_ROWS = [0, 100]

/**
 * What a slider's value means, in detours instead of costs: a point makes a bad
 * street feel 25 % longer, so 4 points = twice as long = up to 100 m detour to skip 100 m of it.
 */
function SliderInfo({
  sliderKey,
  value,
}: {
  sliderKey: SliderKey
  value: number
}) {
  const { t, i18n } = useTranslation()
  const i = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.info.${key}`, values)
  const number = (n: number) => n.toLocaleString(i18n.language)
  const isDanger = sliderKey === 'danger'
  const rows = Array.from(
    new Set([...(isDanger ? DANGER_ROWS : POINT_ROWS), value]),
  ).sort((a, b) => a - b)

  return (
    <>
      <span className="block font-medium text-leaf-ink">
        {i(`${sliderKey}.question`)}
      </span>
      <span className="mt-1 block">
        {rows.map(p => (
          <span
            className={cx(
              'block',
              p === value && 'font-semibold text-leaf-forest',
            )}
            key={p}
          >
            {p} ={' '}
            {p === 0
              ? i('ignore')
              : isDanger
                ? i('dangerRow', { m: p })
                : i('pointsRow', { x: number(1 + p * POINT) })}
            {p === value && ` ${i('yours')}`}
          </span>
        ))}
      </span>
      {!isDanger && value > 0 && (
        <span className="mt-1 block">
          {i(`${sliderKey}.example`, { p: value, m: value * 25 })}
        </span>
      )}
      <span className="mt-1 block text-leaf-muted">
        {i(`${sliderKey}.note`, { lift: value * 25 })}
      </span>
    </>
  )
}

/** The current local time as "YYYY-MM-DDTHH:mm", the format of <input type="datetime-local">. */
function nowForInput(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
}

export default function TripForm({
  startLabel,
  endLabel,
  onStartLabelChange,
  onEndLabelChange,
  onPickStart,
  onPickEnd,
  options,
  onOptionsChange,
  onReset,
  dayMode,
  onDayModeChange,
  daySlider,
  loading = false,
}: TripFormProps) {
  const { t } = useTranslation()
  const hasTime = options.departTime !== ''
  // Decided from the time itself, as the backend does: sun up → shade counts, else lighting.
  const sunUp = isSunUp(options.departTime)
  // The shade data is for 21 July: say so for daytime trips outside the summer months.
  const month = Number(options.departTime.slice(5, 7))
  const outsideSummer = sunUp === true && (month < 5 || month > 8)

  /**
   * Without a departure neither time slider applies; with one, only shade by day or lighting after dark.
   * Through the day both do, each at its own times.
   */
  const timeSliderOff = (key: SliderKey) =>
    !dayMode &&
    (sunUp === null || (key === 'shade' && !sunUp) || (key === 'dark' && sunUp))

  /** Changes one option and keeps the others. */
  const set = <K extends keyof RouteOptions>(key: K, value: RouteOptions[K]) =>
    onOptionsChange({ ...options, [key]: value })

  const renderSlider = (
    { key, min, max, step }: SliderSpec,
    disabled = false,
  ) => (
    // relative: the info panel spans this row.
    <div
      className="relative flex flex-col gap-1 text-sm text-leaf-ink/80"
      key={key}
    >
      <span className="flex items-center gap-1.5">
        <label
          className={disabled ? 'text-leaf-muted/70' : undefined}
          htmlFor={`option-${key}`}
        >
          {t(`greenest.planTrip.penalties.${key}`)}: {options[key]}
        </label>
        <InfoTip
          label={t('greenest.planTrip.info.about', {
            name: t(`greenest.planTrip.penalties.${key}`),
          })}
        >
          <SliderInfo sliderKey={key} value={options[key]} />
        </InfoTip>
      </span>
      <input
        className="accent-leaf-forest disabled:opacity-40"
        disabled={disabled}
        id={`option-${key}`}
        max={max}
        min={min}
        onChange={e => set(key, Number(e.target.value))}
        step={step}
        type="range"
        value={options[key]}
      />
    </div>
  )

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <CardTitle>{t('greenest.planTrip.formTitle')}</CardTitle>
        <p className="text-xs text-leaf-muted">
          {t('greenest.planTrip.clickHint')}
        </p>

        <div className="flex flex-col gap-3">
          <PlaceSearch
            label={t('greenest.planTrip.start')}
            onPick={onPickStart}
            onValueChange={onStartLabelChange}
            pinClassName="text-[#1a7f37]"
            placeholder={t('greenest.planTrip.startPlaceholder')}
            value={startLabel}
          />
          <PlaceSearch
            label={t('greenest.planTrip.destination')}
            onPick={onPickEnd}
            onValueChange={onEndLabelChange}
            pinClassName="text-[#b3261e]"
            placeholder={t('greenest.planTrip.destinationPlaceholder')}
            value={endLabel}
          />
        </div>

        <details className="group rounded-xl border border-leaf-sand/70 p-3">
          <summary className="cursor-pointer text-sm font-medium text-leaf-ink">
            {t('greenest.planTrip.options')}
          </summary>

          <div className="mt-3 flex flex-col gap-4">
            {OPTION_SLIDERS.map(spec => renderSlider(spec))}

            <label className="flex cursor-pointer items-start gap-2 text-sm text-leaf-ink/80">
              <input
                checked={options.preferTime}
                className="mt-0.5 h-4 w-4 accent-leaf-forest"
                onChange={e => set('preferTime', e.target.checked)}
                type="checkbox"
              />
              <span className="flex flex-col">
                {t('greenest.planTrip.preferTime')}
                <span className="text-xs text-leaf-muted">
                  {t('greenest.planTrip.preferTimeHint')}
                </span>
              </span>
            </label>

            {/* relative: the summer-shade info panel spans this block. */}
            <div className="relative flex flex-col gap-1 text-sm text-leaf-ink/80">
              <label htmlFor="depart-time">
                {t('greenest.planTrip.departTime')}
              </label>
              <div className="flex gap-2">
                <input
                  className="min-w-0 flex-1 rounded-lg border border-leaf-sand bg-white px-2 py-1 text-sm disabled:opacity-40"
                  disabled={dayMode}
                  id="depart-time"
                  onChange={e => set('departTime', e.target.value)}
                  type="datetime-local"
                  value={options.departTime}
                />
                <button
                  className="rounded-lg border border-leaf-sand px-2 py-1 text-xs hover:bg-leaf-cream disabled:opacity-40"
                  disabled={dayMode}
                  onClick={() =>
                    set('departTime', hasTime ? '' : nowForInput())
                  }
                  type="button"
                >
                  {hasTime
                    ? t('greenest.planTrip.clearTime')
                    : t('greenest.planTrip.now')}
                </button>
              </div>
              <span className="flex items-center gap-1.5">
                <label className="flex cursor-pointer items-center gap-2">
                  <input
                    checked={dayMode}
                    className="h-4 w-4 accent-leaf-forest"
                    onChange={e => onDayModeChange(e.target.checked)}
                    type="checkbox"
                  />
                  {t('greenest.planTrip.day.toggle')}
                </label>
                <InfoTip
                  label={t('greenest.planTrip.info.about', {
                    name: t('greenest.planTrip.day.toggle'),
                  })}
                >
                  {t('greenest.planTrip.day.info')}
                </InfoTip>
              </span>
              {dayMode ? (
                daySlider
              ) : (
                <span className="text-xs text-leaf-muted">
                  {sunUp === null
                    ? t('greenest.planTrip.departTimeHint')
                    : sunUp
                      ? t('greenest.planTrip.sky.day')
                      : t('greenest.planTrip.sky.night')}
                  {/* The 21 July caveat stays one tap away, so the line is no longer than the night one. */}
                  {outsideSummer && (
                    <InfoTip
                      className="ml-1 align-middle"
                      label={t('greenest.planTrip.info.about', {
                        name: t('greenest.planTrip.penalties.shade'),
                      })}
                    >
                      {t('greenest.planTrip.sky.summerShade')}
                    </InfoTip>
                  )}
                </span>
              )}
            </div>

            {TIME_SLIDERS.map(spec =>
              renderSlider(spec, timeSliderOff(spec.key)),
            )}
          </div>
        </details>

        {loading && (
          <p className="text-xs text-leaf-muted" role="status">
            {t('greenest.planTrip.loading')}
          </p>
        )}

        <button
          className="rounded-full border border-leaf-sand px-4 py-2 text-sm text-leaf-ink hover:bg-leaf-cream"
          onClick={onReset}
          type="button"
        >
          {t('greenest.planTrip.reset')}
        </button>
      </div>
    </Card>
  )
}
