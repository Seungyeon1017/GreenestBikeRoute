'use client'

import { cx } from 'class-variance-authority'
import { useTranslation } from 'react-i18next'
import type { DataAvailability } from '@/types/greenest'

const STYLES: Record<DataAvailability, string> = {
  measured: 'bg-leaf-mint text-leaf-moss ring-leaf-sage/50',
  estimated: 'bg-amber-50 text-amber-800 ring-amber-200',
  demo: 'bg-[#f3ead6] text-[#7a5b1e] ring-[#e6d5ad]',
  mapped: 'bg-sky-50 text-sky-800 ring-sky-200',
  unavailable: 'bg-leaf-cream text-leaf-muted ring-leaf-sand',
}

/** Tells the user whether a value is measured, estimated, mapped in OSM, demo content or missing. */
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
