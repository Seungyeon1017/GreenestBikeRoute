'use client'

import { cx } from 'class-variance-authority'
import { useTranslation } from 'react-i18next'
import type { DataAvailability } from '@/types/greenest'

const STYLES: Record<DataAvailability, string> = {
  measured: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  estimated: 'bg-amber-50 text-amber-700 ring-amber-200',
  demo: 'bg-violet-50 text-violet-700 ring-violet-200',
  unavailable: 'bg-stone-100 text-stone-500 ring-stone-200',
}

/** Tells the user whether a value is measured, estimated, demo content or missing. */
export default function AvailabilityBadge({
  availability,
  className,
}: {
  availability: DataAvailability
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <span
      className={cx(
        'inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
        STYLES[availability],
        className,
      )}
    >
      {t(`greenest.availability.${availability}`)}
    </span>
  )
}
