'use client'

import { Navigation } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type { RoutePreferences } from '@/types/greenest'

export type TripFormValues = {
  start: string
  destination: string
  preferences: RoutePreferences
}

type TripFormProps = {
  values: TripFormValues
  onChange: (_values: TripFormValues) => void
  onSubmit: () => void
  loading?: boolean
}

const PREFERENCE_KEYS = [
  'preferGreener',
  'preferQuieter',
  'preferCycleLanes',
] as const

const inputClass =
  'w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/30'

export default function TripForm({
  values,
  onChange,
  onSubmit,
  loading = false,
}: TripFormProps) {
  const { t } = useTranslation()
  const { preferences } = values
  const canSubmit =
    values.start.trim() !== '' && values.destination.trim() !== '' && !loading

  const setPreference = <K extends keyof RoutePreferences>(
    key: K,
    value: RoutePreferences[K],
  ) => onChange({ ...values, preferences: { ...preferences, [key]: value } })

  return (
    <Card>
      <form
        className="flex flex-col gap-4"
        onSubmit={event => {
          event.preventDefault()
          if (canSubmit) {
            onSubmit()
          }
        }}
      >
        <CardTitle>{t('greenest.planTrip.formTitle')}</CardTitle>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-stone-600" htmlFor="start">
            {t('greenest.planTrip.start')}
          </label>
          <input
            autoComplete="off"
            className={inputClass}
            id="start"
            onChange={e => onChange({ ...values, start: e.target.value })}
            placeholder={t('greenest.planTrip.startPlaceholder')}
            value={values.start}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label
            className="text-xs font-medium text-stone-600"
            htmlFor="destination"
          >
            {t('greenest.planTrip.destination')}
          </label>
          <input
            autoComplete="off"
            className={inputClass}
            id="destination"
            onChange={e => onChange({ ...values, destination: e.target.value })}
            placeholder={t('greenest.planTrip.destinationPlaceholder')}
            value={values.destination}
          />
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-xs font-medium text-stone-600">
            {t('greenest.planTrip.preferences')}
          </legend>
          {PREFERENCE_KEYS.map(key => (
            <label
              className="flex cursor-pointer items-center gap-2 text-sm text-stone-700"
              key={key}
            >
              <input
                checked={preferences[key]}
                className="h-4 w-4 accent-emerald-600"
                onChange={e => setPreference(key, e.target.checked)}
                type="checkbox"
              />
              {t(`greenest.planTrip.${key}`)}
            </label>
          ))}
          <label
            className="mt-1 flex flex-col gap-1 text-sm text-stone-700"
            htmlFor="max-extra"
          >
            <span>
              {t('greenest.planTrip.maxExtraMinutes', {
                minutes: preferences.maxExtraMinutes,
              })}
            </span>
            <input
              className="accent-emerald-600"
              id="max-extra"
              max={30}
              min={0}
              onChange={e =>
                setPreference('maxExtraMinutes', Number(e.target.value))
              }
              step={1}
              type="range"
              value={preferences.maxExtraMinutes}
            />
          </label>
        </fieldset>

        <button
          className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
          disabled={!canSubmit}
          type="submit"
        >
          <Navigation aria-hidden className="h-4 w-4" />
          {t('greenest.planTrip.findRoute')}
        </button>
      </form>
    </Card>
  )
}
