'use client'

import Title from '@/components/Elements/Title'
import Image from 'next/image'
import Link from 'next/link'
import Container from '../Container'
import StairStepBackground from '../StairStepBackground'
import { useTranslation } from 'react-i18next'

import reeduLogo from '@/assets/logos/reedu_Logo_horizontal_orange.png'
import arkadiaLogo from '@/assets/logos/Wortmarke.svg'
import aimLogo from '@/assets/logos/aim_logo.png'
import ContactFormTile from '@/components/Tiles/Contact/ContactFormTile'

export default function Footer() {
  const { t } = useTranslation()
  return (
    <StairStepBackground>
      <ContactFormTile />
      <Container>
        <div className="items-top flex w-full flex-col justify-around pb-10 lg:flex-row lg:gap-20 xl:pb-20 2xl:gap-44">
          <div className="flex-1">
            <Title as={'h4'} className="py-10 md:py-20">
              {t('footer.projectOf')}
            </Title>
            <div className="flex w-full grid-cols-2 flex-col gap-8 lg:gap-16 xl:grid">
              <div className="relative h-28 w-full max-w-[400px] rounded-md md:h-36">
                <Link href="https://arkadia.hn/" target="_blank">
                  <Image
                    alt="Arkadia Logo"
                    className="object-contain"
                    fill
                    src={arkadiaLogo}
                  />
                </Link>
              </div>
              <div className="relative h-28 w-full max-w-[400px] rounded-md md:h-36">
                <Link href="https://reedu.de/" target="_blank">
                  <Image
                    alt="Reedu Logo"
                    className="object-contain"
                    fill
                    src={reeduLogo}
                  />
                </Link>
              </div>
              <div className="relative h-28 w-full max-w-[400px] rounded-md md:h-36">
                <Link href="https://www.aim-akademie.org/" target="_blank">
                  <Image
                    alt="AIM Logo"
                    className="object-contain"
                    fill
                    src={aimLogo}
                  />
                </Link>
              </div>
            </div>
          </div>

          <div className="sm:hidden flex flex-1 flex-col 2xl:flex">
            <Title as={'h4'} className="py-10 opacity-0 md:py-20">
              {t('footer.impressum')}
            </Title>
            <div className="flex flex-1 flex-col justify-between gap-8">
              <Link href="/impressum">
                <Title as="h5" className="underline" variant={'primary'}>
                  {t('footer.impressum')}
                </Title>
              </Link>
              <Link href="/datenschutz">
                <Title as="h5" className="underline" variant={'primary'}>
                  {t('footer.datenschutz')}
                </Title>
              </Link>
              {/* <Link href="/feedback#feedback">
                <Title as="h5" className="underline" variant={'primary'}>
                  {t('footer.giveFeedback')}
                </Title>
              </Link> */}
            </div>
          </div>
        </div>
        <div className="sm:flex hidden justify-between 2xl:hidden">
          <Link href="/impressum">
            <Title as="h5" className="underline" variant={'primary'}>
              {t('footer.impressum')}
            </Title>
          </Link>
          <Link href="/datenschutz">
            <Title as="h5" className="underline" variant={'primary'}>
              {t('footer.datenschutz')}
            </Title>
          </Link>
          <Link href="/feedback#feedback">
            <Title as="h5" className="underline" variant={'primary'}>
              {t('footer.giveFeedback')}
            </Title>
          </Link>
        </div>
      </Container>
    </StairStepBackground>
  )
}
