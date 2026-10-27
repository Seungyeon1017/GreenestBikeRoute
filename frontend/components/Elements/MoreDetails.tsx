'use client'

import Link from 'next/link'
import type { VariantProps } from 'class-variance-authority'
import { cva, cx } from 'class-variance-authority'
import Title from './Title'
import { MsKlimadashboardIconsNaviInfoI } from '../Icons/Misc/Navi'
import { useTranslation } from 'react-i18next'

const style = cva('flex cursor-pointer items-center gap-1 md:gap-3', {
  variants: {
    variant: {
      primary: 'text-primary',
      inverse: 'text-white',
    },
  },
  defaultVariants: {
    variant: 'primary',
  },
})

export type MoreDetailsProps = VariantProps<typeof style> & {
  link?: string
  className?: string
  lessDetails?: boolean
  onClick?: () => void
}

export default function MoreDetails({
  link,
  variant,
  className,
  lessDetails,
  onClick,
}: MoreDetailsProps) {
  const { t } = useTranslation()
  const Details = (
    <div className={cx(style({ variant }), className)} onClick={onClick}>
      <MsKlimadashboardIconsNaviInfoI className="h-6" />
      <Title as="h6" className="whitespace-nowrap underline">
        {lessDetails ? t('common.lessDetails') : t('common.moreDetails')}
      </Title>
    </div>
  )

  if (!link) {
    return Details
  }

  return <Link href={link}>{Details}</Link>
}
