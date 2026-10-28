'use client'

import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { LngLat, RouteOptions } from '@/types/greenest'

type TripFormProps = {
  start: LngLat | null
  end: LngLat | null
  options: RouteOptions
  onOptionsChange: (_options: RouteOptions) => void
  onReset: () => void
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

/** Always visible. Min, max and step match the backend limits. */
const MAIN_SLIDERS: SliderSpec[] = [
  { key: 'bump', min: 0, max: 50, step: 1 },
  { key: 'danger', min: 0, max: 100, step: 5 },
  { key: 'pm', min: 0, max: 5, step: 0.25 },
]

/** Under "More options". */
const MORE_SLIDERS: SliderSpec[] = [
  { key: 'stop', min: 0, max: 5, step: 0.25 },
  { key: 'bikeFriendly', min: 0, max: 5, step: 0.25 },
]

/** Only used by the backend when a departure time is set. */
const TIME_SLIDERS: SliderSpec[] = [
  { key: 'shade', min: 0, max: 5, step: 0.25 },
  { key: 'dark', min: 0, max: 5, step: 0.25 },
]

/** Shows a point as "lat, lng" rounded to five decimals, or a placeholder. */
function formatPoint(point: LngLat | null, notSet: string): string {
  return point ? `${point[1].toFixed(5)}, ${point[0].toFixed(5)}` : notSet
}

/** The current local time as "YYYY-MM-DDTHH:mm", the format of <input type="datetime-local">. */
function nowForInput(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
}

export default function TripForm({
  start,
  end,
  options,
  onOptionsChange,
  onReset,
  loading = false,
}: TripFormProps) {
  const { t } = useTranslation()
  const notSet = t('greenest.planTrip.notSet')
  const hasTime = options.departTime !== ''

  /** Changes one option and keeps the others. */
  const set = <K extends keyof RouteOptions>(key: K, value: RouteOptions[K]) =>
    onOptionsChange({ ...options, [key]: value })

  const renderSlider = (
    { key, min, max, step }: SliderSpec,
    disabled = false,
  ) => (
    <label
      className="flex flex-col gap-1 text-sm text-leaf-ink/80"
      htmlFor={`option-${key}`}
      key={key}
    >
      <span className={disabled ? 'text-leaf-muted/70' : undefined}>
        {t(`greenest.planTrip.penalties.${key}`)}: {options[key]}
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
    </label>
  )

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <CardTitle>{t('greenest.planTrip.formTitle')}</CardTitle>
        <p className="text-xs text-leaf-muted">
          {t('greenest.planTrip.clickHint')}
        </p>

        <dl className="flex flex-col gap-1 text-sm text-leaf-ink/80">
          <div className="flex justify-between gap-2">
            <dt>{t('greenest.planTrip.startPoint')}</dt>
            <dd className="tabular-nums">{formatPoint(start, notSet)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>{t('greenest.planTrip.endPoint')}</dt>
            <dd className="tabular-nums">{formatPoint(end, notSet)}</dd>
          </div>
        </dl>

        {MAIN_SLIDERS.map(spec => renderSlider(spec))}

        <details className="group rounded-xl border border-leaf-sand/70 p-3">
          <summary className="cursor-pointer text-sm font-medium text-leaf-ink">
            {t('greenest.planTrip.moreOptions')}
          </summary>

          <div className="mt-3 flex flex-col gap-4">
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

            {MORE_SLIDERS.map(spec => renderSlider(spec))}

            <div className="flex flex-col gap-1 text-sm text-leaf-ink/80">
              <label htmlFor="depart-time">
                {t('greenest.planTrip.departTime')}
              </label>
              <div className="flex gap-2">
                <input
                  className="min-w-0 flex-1 rounded-lg border border-leaf-sand bg-white px-2 py-1 text-sm"
                  id="depart-time"
                  onChange={e => set('departTime', e.target.value)}
                  type="datetime-local"
                  value={options.departTime}
                />
                <button
                  className="rounded-lg border border-leaf-sand px-2 py-1 text-xs hover:bg-leaf-cream"
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
              <span className="text-xs text-leaf-muted">
                {t('greenest.planTrip.departTimeHint')}
              </span>
            </div>

            {TIME_SLIDERS.map(spec => renderSlider(spec, !hasTime))}
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


/* 'use client'

import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { LngLat, Penalties, RoutePreferences } from '@/types/greenest'

export type TripFormValues = {
  start: string
  destination: string
  preferences: RoutePreferences
}

type TripFormProps = {
  start: LngLat | null
  end: LngLat | null
  penalties: Penalties
  onPenaltiesChange: (_penalties: Penalties) => void
  onReset: () => void
  loading?: boolean
}

//One slider per penalty. Min, max and step match the backend limits. 
const SLIDERS = [
  { key: 'bump', min: 0, max: 50, step: 1 },
  { key: 'danger', min: 0, max: 100, step: 5 },
  { key: 'pm', min: 0, max: 5, step: 0.25 },
] as const

//Shows a point as "lat, lng" rounded to five decimals, or a placeholder. 
function formatPoint(point: LngLat | null, notSet: string): string {
  return point ? `${point[1].toFixed(5)}, ${point[0].toFixed(5)}` : notSet
}

export default function TripForm({
  start,
  end,
  penalties,
  onPenaltiesChange,
  onReset,
  loading = false,
}: TripFormProps) {
  const { t } = useTranslation()
  const notSet = t('greenest.planTrip.notSet')

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <CardTitle>{t('greenest.planTrip.formTitle')}</CardTitle>
        <p className="text-xs text-leaf-muted">{t('greenest.planTrip.clickHint')}</p>

        <dl className="flex flex-col gap-1 text-sm text-leaf-ink/80">
          <div className="flex justify-between gap-2">
            <dt>{t('greenest.planTrip.startPoint')}</dt>
            <dd className="tabular-nums">{formatPoint(start, notSet)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>{t('greenest.planTrip.endPoint')}</dt>
            <dd className="tabular-nums">{formatPoint(end, notSet)}</dd>
          </div>
        </dl>

        {SLIDERS.map(({ key, min, max, step }) => (
          <label
            className="flex flex-col gap-1 text-sm text-leaf-ink/80"
            htmlFor={`penalty-${key}`}
            key={key}
          >
            <span>
              {t(`greenest.planTrip.penalties.${key}`)}: {penalties[key]}
            </span>
            <input
              className="accent-leaf-forest"
              id={`penalty-${key}`}
              max={max}
              min={min}
              onChange={e =>
                onPenaltiesChange({ ...penalties, [key]: Number(e.target.value) })
              }
              step={step}
              type="range"
              value={penalties[key]}
            />
          </label>
        ))}

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
} */
