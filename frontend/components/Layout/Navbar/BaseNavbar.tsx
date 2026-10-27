'use client'

import Collapsible from '@/components/Elements/Collapsible'
import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'
import { MsKlimadashboardIconsNaviBookmark } from '@/components/Icons/Misc/Navi'
import { Bars3Icon } from '@heroicons/react/24/outline'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import Container from '../Container'
import StairStepBackground from '../StairStepBackground'
import LanguageSwitcher from './LanguageSwitcher'
import LinkComponent, { LinkProps } from './LinkComponent'
import { Theme } from '@prisma/client'

type BaseNavbarProps = {
  actionComponent?: React.ReactElement
  variant?: 'primary' | 'secondary' | 'overlay'
  headerTitle?: string
  headerDescription?: string
  children?: React.ReactElement | React.ReactElement[]
}

export default function BaseNavbar({
  actionComponent,
  variant = 'primary',
  headerTitle,
  headerDescription,
  children,
}: BaseNavbarProps) {
  const [theme, setTheme] = useState<Theme | null>(null)
  const [links, setLinks] = useState<LinkProps[]>([])
  const hasHeader = Boolean(headerTitle || headerDescription)

  useEffect(() => {
    const fetchTheme = async () => {
      const response = await fetch('/api/theme')
      if (response.ok) {
        const theme = await response.json()
        setTheme(theme)
      }
    }
    fetchTheme()
  }, [])

  useEffect(() => {
    const fetchLinks = async () => {
      const response = await fetch('/api/pages')
      if (!response.ok) {
        return
      }

      const data = await response.json()
      const pages: Array<{ slug: string; title: string }> = data?.pages ?? []

      setLinks(
        pages.map(page => ({
          title: page.title,
          link: `/pages/${page.slug}`,
          icon: MsKlimadashboardIconsNaviBookmark,
        })),
      )
    }

    fetchLinks()
  }, [])

  return (
    <div className="pt-8">
      <StairStepBackground variant={variant}>
        <Container>
          <div className="xl:hidden">
            <Collapsible
              trigger={
                <div className="w-fit rounded-lg border-2 border-primary p-2 md:p-4">
                  <Bars3Icon className="w-5 stroke-2 text-primary md:w-6" />
                </div>
              }
            >
              <div className="my-4 flex flex-col flex-wrap gap-2 md:flex-row">
                {links.map(link => (
                  <LinkComponent
                    key={link.link}
                    variant={variant === 'overlay' ? 'inverse' : 'primary'}
                    {...link}
                  />
                ))}
              </div>
            </Collapsible>
            <Spacer size={'sm'} />
          </div>
          <div className="flex flex-col justify-between gap-4">
            <Link href={'/'}>
              <Title
                as="h2"
                variant={variant === 'overlay' ? 'inverse' : 'primary'}
              >
                {theme?.title || 'Green City Heilbronn'}
              </Title>
            </Link>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">{actionComponent}</div>

              <div className="flex items-center gap-4">
                <div className="hidden h-fit flex-wrap justify-end gap-2 xl:flex">
                  {links.map(link => (
                    <LinkComponent
                      key={link.link}
                      variant={variant === 'overlay' ? 'inverse' : 'primary'}
                      {...link}
                    />
                  ))}
                </div>
                <LanguageSwitcher />
              </div>
            </div>
          </div>
          {hasHeader && (
            <>
              <Spacer size={'xl'} />
              <div className="flex w-full flex-col-reverse gap-2 md:flex-row">
                {headerDescription ? (
                  <Title as={'h5'} className="flex-[2_2_0%]" variant="primary">
                    {headerDescription}
                  </Title>
                ) : (
                  <div className="flex-[2_2_0%]" />
                )}
                <div className="hidden flex-1 md:block" />
                {headerTitle ? (
                  <Title as={'h2'} className="flex-1" variant="secondary">
                    {headerTitle}
                  </Title>
                ) : (
                  <div className="flex-1" />
                )}
              </div>
            </>
          )}
          {children && (
            <>
              <Spacer size={'xl'} />
              {children}
            </>
          )}
        </Container>
      </StairStepBackground>
    </div>
  )
}
