'use client'

import { ArrowRight, Map as MapIcon, Route } from 'lucide-react'
import Link from 'next/link'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import AvailabilityBadge from '@/components/Greenest/ui/AvailabilityBadge'
import Card from '@/components/Greenest/ui/Card'
import { EXPERIENCES, SAMPLE_PLACES } from './content'
import PlaceCard from './PlaceCard'

function SectionHeading({ title, text }: { title: string; text: string }) {
  return (
    <div className="space-y-1">
      <h2 className="font-lexend text-xl font-bold text-stone-900">{title}</h2>
      <p className="text-sm text-stone-600">{text}</p>
    </div>
  )
}

export default function HighlightsView() {
  const { t } = useTranslation()

  return (
    <div className="mx-auto flex w-full max-w-[1920px] flex-col gap-10 px-4 py-6 md:px-8">
      {/* Intro */}
      <section className="grid gap-6 overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-700 to-emerald-500 p-6 text-white shadow-sm md:p-10 lg:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex flex-col justify-center gap-4">
          <h1 className="font-lexend text-3xl font-bold md:text-4xl">
            {t('greenest.highlights.title')}
          </h1>
          <p className="max-w-xl text-emerald-50">
            {t('greenest.highlights.subtitle')}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              className="flex items-center gap-2 rounded-xl bg-white px-4 py-2 text-sm font-semibold text-emerald-700 shadow-sm hover:bg-emerald-50"
              href="/overview"
            >
              <MapIcon aria-hidden className="h-4 w-4" />
              {t('greenest.highlights.exploreOnMap')}
            </Link>
            <Link
              className="flex items-center gap-2 rounded-xl border border-white/60 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10"
              href="/plan-trip"
            >
              <Route aria-hidden className="h-4 w-4" />
              {t('greenest.highlights.planTrip')}
            </Link>
          </div>
        </div>
        <div className="h-56 overflow-hidden rounded-2xl bg-white ring-1 ring-white/30 lg:h-full lg:min-h-[14rem]">
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
        <Card className="flex flex-col items-start gap-2 bg-stone-50 md:flex-row md:items-center">
          <AvailabilityBadge availability="unavailable" />
          <p className="text-sm text-stone-600">
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
          {EXPERIENCES.map(({ id, emoji }) => (
            <Card className="flex flex-col gap-2" key={id}>
              <span aria-hidden className="text-2xl">
                {emoji}
              </span>
              <h3 className="font-lexend text-base font-bold text-stone-900">
                {t(`greenest.highlights.experiences.${id}.title`)}
              </h3>
              <p className="flex-1 text-sm text-stone-600">
                {t(`greenest.highlights.experiences.${id}.text`)}
              </p>
              <Link
                className="flex items-center gap-1 self-start text-sm font-medium text-emerald-700 hover:text-emerald-800"
                href="/plan-trip"
              >
                {t('greenest.highlights.planTrip')}
                <ArrowRight aria-hidden className="h-4 w-4" />
              </Link>
            </Card>
          ))}
        </div>
      </section>
    </div>
  )
}
