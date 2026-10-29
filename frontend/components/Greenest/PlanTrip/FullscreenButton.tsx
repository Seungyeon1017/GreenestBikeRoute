'use client'

import { Maximize2, Minimize2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

type Props = {
  full: boolean
  onToggle: () => void
}

/** Enlarges the map to the whole screen and back. Phones and tablets only (below `lg`). */
export default function FullscreenButton({ full, onToggle }: Props) {
  const { t } = useTranslation()
  const label = t(
    full ? 'greenest.planTrip.exitFullscreen' : 'greenest.planTrip.fullscreen',
  )
  const Icon = full ? Minimize2 : Maximize2
  return (
    // Top left: MapLibre's zoom buttons and Report a problem take the top right.
    <button
      aria-label={label}
      aria-pressed={full}
      className="absolute left-2.5 top-2.5 z-10 inline-flex h-9 w-9 items-center justify-center rounded-full border border-leaf-sand bg-white text-leaf-forest shadow-soft hover:bg-leaf-cream lg:hidden"
      onClick={onToggle}
      title={label}
      type="button"
    >
      <Icon aria-hidden className="h-4 w-4" />
    </button>
  )
}
