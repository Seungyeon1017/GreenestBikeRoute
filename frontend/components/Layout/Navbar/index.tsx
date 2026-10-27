'use client'

import { Button } from '../../Elements/Button'

import Back from '@/components/Elements/Back'
import Title from '@/components/Elements/Title'
import { MsKlimadashboardIconsNaviInfoI } from '@/components/Icons/Misc/Navi'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { AnimatePresence, motion } from 'framer-motion'
import { usePathname } from 'next/navigation'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import SectionTitle from '../SectionTitle'
import BaseNavbar from './BaseNavbar'

const routeToType: {
  [key: string]: 'impressum' | 'datenschutz' | 'feedback'
} = {
  impressum: 'impressum',
  datenschutz: 'datenschutz',
  feedback: 'feedback',
}

export default function Navbar({
  large,
  aboutButton,
}: {
  large?: boolean
  aboutButton?: { title: string; text: string }
}) {
  const pathname = usePathname()
  const { t } = useTranslation()
  const [showOverlay, setShowOverlay] = useState(false)

  if (!pathname) {
    return <BaseNavbar></BaseNavbar>
  }

  const isIndexPage = pathname === '/'
  const [_, route] = pathname?.split('/')

  const ActionComponent = isIndexPage ? (
    aboutButton?.text ? (
      <Button
        className="whitespace-nowrap"
        onClick={() => setShowOverlay(true)}
        size={'link'}
        startIcon={
          <MsKlimadashboardIconsNaviInfoI className="h-[26px] md:h-[34px]" />
        }
        variant={'secondary'}
      >
        {aboutButton.title}
      </Button>
    ) : (
      <></>
    )
  ) : (
    <Back variant={route in routeToType ? 'inverse' : 'primary'} />
  )

  const InfoText = (
    <div className="lg:w-2/3 2xl:w-1/3">
      <Title as={'h5'} variant={'inverse'}>
        {aboutButton?.text}
      </Title>
    </div>
  )

  const OverlayNavbar = (
    <BaseNavbar
      actionComponent={
        <Button
          className="whitespace-nowrap"
          onClick={() => setShowOverlay(false)}
          size={'link'}
          startIcon={<XMarkIcon className="h-[26px] text-white md:h-[34px]" />}
          variant={'secondary'}
        >
          <Title as="h5" variant={'inverse'}>
            {t('navbar.hideInfo')}
          </Title>
        </Button>
      }
      variant="overlay"
    >
      {InfoText}
    </BaseNavbar>
  )

  if (isIndexPage) {
    return (
      <div className="relative">
        <BaseNavbar actionComponent={ActionComponent}>
          {large ? <div className="h-40" /> : <></>}
        </BaseNavbar>
        <AnimatePresence>
          {showOverlay && (
            <motion.div
              animate={{ opacity: 1 }}
              className="absolute left-0 top-0 z-10 h-full w-full"
              exit={{ opacity: 0 }}
              initial={{ opacity: 0 }}
            >
              {OverlayNavbar}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    )
  }

  if (route in routeToType) {
    return (
      <BaseNavbar actionComponent={ActionComponent} variant="overlay">
        <div className="flex flex-col gap-2 lg:flex-row lg:gap-0">
          <div className="flex-1" />
          <div className="flex flex-1 justify-end">
            <SectionTitle large variant={routeToType[route]} />
          </div>
        </div>
      </BaseNavbar>
    )
  }

  return <BaseNavbar actionComponent={ActionComponent}></BaseNavbar>
}
