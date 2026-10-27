'use client'

import { Info } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import RouteComparison from './RouteComparison'
import TripForm, { type TripFormValues } from './TripForm'

const INITIAL_VALUES: TripFormValues = {
  start: '',
  destination: '',
  preferences: {
    preferGreener: true,
    preferQuieter: false,
    preferCycleLanes: true,
    maxExtraMinutes: 10,
  },
}

export default function PlanTripView() {
  const { t } = useTranslation()
  const [values, setValues] = useState(INITIAL_VALUES)
  // Address search and the call to services/greenestApi.fetchRoute arrive in Phase 4.
  const [submitted, setSubmitted] = useState(false)

  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8">
      <PageIntro
        eyebrow={t('greenest.planTrip.eyebrow')}
        subtitle={t('greenest.planTrip.subtitle')}
        title={t('greenest.planTrip.title')}
      />
      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <TripForm
            onChange={next => {
              setValues(next)
              setSubmitted(false)
            }}
            onSubmit={() => setSubmitted(true)}
            values={values}
          />
          {submitted && (
            <p
              className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
              role="status"
            >
              <Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
              {t('greenest.planTrip.notConnected')}
            </p>
          )}
          <RouteComparison />
        </div>
        <section className="h-[60vh] min-h-[420px] overflow-hidden rounded-3xl border border-leaf-sand shadow-soft lg:h-auto">
          <BaseMap ariaLabel={t('greenest.planTrip.mapLabel')} />
        </section>
      </div>
    </div>
  )
}
