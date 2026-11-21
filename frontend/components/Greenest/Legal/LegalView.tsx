'use client'

import { TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import PageIntro from '@/components/Greenest/ui/PageIntro'

type Section = { heading: string; lines: string[] }

/** Text in [square brackets] is a fact still missing: keep it visible until it is filled in. */
function LegalLine({ text }: { text: string }) {
  return (
    <p>
      {text.split(/(\[[^\]]+\])/).map((part, i) =>
        part.startsWith('[') ? (
          <mark className="rounded bg-amber-200 px-1 text-leaf-ink" key={i}>
            {part}
          </mark>
        ) : (
          part
        ),
      )}
    </p>
  )
}

/** The Impressum or Datenschutz page, in the active language. */
export default function LegalView({ page }: { page: 'imprint' | 'privacy' }) {
  const { t } = useTranslation()
  const sections = t(`greenest.legal.${page}.sections`, {
    returnObjects: true,
  }) as unknown as Section[]

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 px-4 py-6 md:px-8">
      <PageIntro
        subtitle={t(`greenest.legal.${page}.subtitle`)}
        title={t(`greenest.legal.${page}.title`)}
      />
      <aside className="flex gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-leaf-ink">
        <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{t('greenest.legal.draftTitle')}</p>
          <p>{t('greenest.legal.draftText')}</p>
        </div>
      </aside>
      {sections.map(section => (
        <section className="space-y-2" key={section.heading}>
          <h2 className="font-display text-xl font-medium text-leaf-forest">
            {section.heading}
          </h2>
          <div className="space-y-2 text-sm leading-relaxed">
            {section.lines.map(line => (
              <LegalLine key={line} text={line} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}
