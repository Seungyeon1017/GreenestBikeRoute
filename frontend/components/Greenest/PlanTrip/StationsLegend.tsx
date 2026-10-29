'use client'

import { TrainFront } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import { SBAHN_COLOR, TRAIN_COLOR } from './transitLayers'

/** On the map while the Stations layer is on: what the S disc and the train disc mean. */
export default function StationsLegend({ error }: { error: string | null }) {
  const { t } = useTranslation()

  return (
    <div className="pointer-events-auto relative flex flex-col gap-1.5 rounded-2xl border border-leaf-sand bg-white px-3 py-2 text-xs text-leaf-ink shadow-soft">
      <div className="flex items-center gap-1.5">
        <strong className="text-sm text-leaf-forest">
          {t('greenest.planTrip.stations.title')}
        </strong>
        <InfoTip
          above
          label={t('greenest.planTrip.info.about', {
            name: t('greenest.planTrip.stations.title'),
          })}
        >
          {t('greenest.planTrip.stations.hint')}
          <span className="mt-1 block text-leaf-muted">
            {t('greenest.planTrip.stations.credit')}
          </span>
        </InfoTip>
      </div>
      {error ? (
        <p className="text-red-700" role="alert">
          {error}
        </p>
      ) : (
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold leading-none text-white"
              style={{ backgroundColor: SBAHN_COLOR }}
            >
              S
            </span>
            {t('greenest.planTrip.stations.sbahn')}
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="flex h-4 w-4 items-center justify-center rounded-full text-white"
              style={{ backgroundColor: TRAIN_COLOR }}
            >
              <TrainFront className="h-2.5 w-2.5" strokeWidth={2.5} />
            </span>
            {t('greenest.planTrip.stations.train')}
          </span>
        </div>
      )}
    </div>
  )
}
