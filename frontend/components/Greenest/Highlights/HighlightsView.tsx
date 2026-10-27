'use client'

import {
  ArrowRight,
  Bird,
  type LucideIcon,
  Map as MapIcon,
  Moon,
  Route,
  Trees,
  Waves,
} from 'lucide-react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card from '@/components/Greenest/ui/Card'
import { EXPERIENCES, SAMPLE_PLACES } from './content'
import PlaceCard from './PlaceCard'

const EXPERIENCE_ICONS: Record<(typeof EXPERIENCES)[number], LucideIcon> = {
  scenicGreen: Trees,
  quietEscape: Moon,
  riverside: Waves,
  nature: Bird,
}

function SectionHeading({ title, text }: { title: string; text: string }) {
  return (
    <div className="space-y-1.5">
      <h2 className="font-display text-2xl font-medium tracking-tight text-leaf-forest md:text-3xl">
        {title}
      </h2>
      <p className="text-sm leading-relaxed text-leaf-muted">{text}</p>
    </div>
  )
}

export default function HighlightsView() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-10 px-4 py-6 md:px-8">
      {/* Intro */}
      <section className="relative grid gap-6 overflow-hidden rounded-[2rem] bg-leaf-forest p-6 text-leaf-cream shadow-soft md:p-12 lg:grid-cols-[minmax(0,1fr)_26rem]">
        {/* Soft light spots for depth */}
        <div
          aria-hidden
          className="pointer-events-none absolute -left-24 -top-24 h-72 w-72 rounded-full bg-leaf-fern/40 blur-3xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-32 right-1/3 h-80 w-80 rounded-full bg-leaf-sage/20 blur-3xl"
        />
        <div className="relative flex flex-col justify-center gap-5">
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-leaf-sage">
            {t('greenest.highlights.eyebrow')}
          </p>
          <h1 className="font-display text-4xl font-medium leading-tight tracking-tight md:text-5xl">
            {t('greenest.highlights.title')}
          </h1>
          <p className="max-w-xl leading-relaxed text-leaf-cream/80">
            {t('greenest.highlights.subtitle')}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              className="flex items-center gap-2 rounded-full bg-leaf-cream px-5 py-2.5 text-sm font-semibold text-leaf-forest shadow-sm transition-colors hover:bg-leaf-mint"
              href="/overview"
            >
              <MapIcon aria-hidden className="h-4 w-4" />
              {t('greenest.highlights.exploreOnMap')}
            </Link>
            <Link
              className="flex items-center gap-2 rounded-full border border-leaf-cream/40 px-5 py-2.5 text-sm font-semibold text-leaf-cream transition-colors hover:bg-leaf-cream/10"
              href="/plan-trip"
            >
              <Route aria-hidden className="h-4 w-4" />
              {t('greenest.highlights.planTrip')}
            </Link>
          </div>
        </div>
        <div className="relative h-56 overflow-hidden rounded-3xl bg-leaf-cream ring-1 ring-leaf-cream/20 lg:h-full lg:min-h-[16rem]">
          <BaseMap ariaLabel={t('greenest.highlights.mapLabel')} zoom={12} />
        </div>
      </section>

      {/* A. Explore Green Places */}
      <section className="flex flex-col gap-4">
        <SectionHeading
          text={t('greenest.highlights.placesText')}
          title={t('greenest.highlights.placesTitle')}
        />
        <div className="grid gap-4 xs:grid-cols-2 lg:grid-cols-4">
          {SAMPLE_PLACES.map(place => (
            <PlaceCard key={place.id} place={place} />
          ))}
        </div>
      </section>

      {/* B. Greenest Roads */}
      <section className="flex flex-col gap-4">
        <SectionHeading
          text={t('greenest.highlights.roadsText')}
          title={t('greenest.highlights.roadsTitle')}
        />
        <Card className="flex flex-col items-start gap-2 bg-leaf-cream md:flex-row md:items-center">
          <AvailabilityBadge availability="unavailable" />
          <p className="text-sm text-leaf-muted">
            {t('greenest.highlights.roadsEmpty')}
          </p>
        </Card>
      </section>

      {/* C. Suggested Cycling Experiences */}
      <section className="flex flex-col gap-4">
        <SectionHeading
          text={t('greenest.highlights.experiencesText')}
          title={t('greenest.highlights.experiencesTitle')}
        />
        <div className="grid gap-4 xs:grid-cols-2 lg:grid-cols-4">
          {EXPERIENCES.map(id => {
            const Icon = EXPERIENCE_ICONS[id]
            return (
              <Card
                className="group flex flex-col gap-3 transition-transform hover:-translate-y-0.5"
                key={id}
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-full bg-leaf-mint text-leaf-moss transition-colors group-hover:bg-leaf-forest group-hover:text-leaf-cream">
                  <Icon aria-hidden className="h-5 w-5" />
                </span>
                <h3 className="font-display text-lg font-medium text-leaf-forest">
                  {t(`greenest.highlights.experiences.${id}.title`)}
                </h3>
                <p className="flex-1 text-sm text-leaf-muted">
                  {t(`greenest.highlights.experiences.${id}.text`)}
                </p>
                <Link
                  className="flex items-center gap-1 self-start text-sm font-medium text-leaf-moss hover:text-leaf-forest"
                  href="/plan-trip"
                >
                  {t('greenest.highlights.planTrip')}
                  <ArrowRight aria-hidden className="h-4 w-4" />
                </Link>
              </Card>
            )
          })}
        </div>
      </section>
    </div>
  )
}
