import { useTranslation } from 'react-i18next'
import type { RouteTag } from '@/types/users'

/** The route's tags as small chips, with "Runde" first for a loop. */
export default function TagList({
  tags,
  isLoop,
}: {
  tags: RouteTag[]
  isLoop: boolean
}) {
  const { t } = useTranslation()
  const labels = [
    ...(isLoop ? [t('greenest.ridersRoutes.loop')] : []),
    ...tags.map(tag => t(`greenest.ridersRoutes.tags.${tag}`)),
  ]
  if (!labels.length) {
    return null
  }
  return (
    <ul className="flex flex-wrap gap-1">
      {labels.map(label => (
        <li
          className="rounded-full bg-leaf-mint px-2 py-0.5 text-[11px] font-medium text-leaf-moss"
          key={label}
        >
          {label}
        </li>
      ))}
    </ul>
  )
}
