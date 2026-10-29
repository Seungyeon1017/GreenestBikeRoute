'use client'

import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import type { ClosureFeature, ClosureProperties } from '@/types/greenest'
import { CLOSURE_COLORS, MAPPING_COLOR } from './reportLayers'

const HEILBRONN_TZ = 'Europe/Berlin'

/**
 * When a closure lapses, in Heilbronn time: "until Thu 5 Nov, 14:00", or
 * "through Mon 2 Nov" when it ends at midnight (a reporter's last day).
 */
function until(iso: string, t: TFunction, lang: string): string {
  const end = new Date(iso)
  const clock = end.toLocaleTimeString('en-GB', {
    timeZone: HEILBRONN_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  })
  const day = {
    timeZone: HEILBRONN_TZ,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  } as const
  if (clock === '00:00') {
    return t('greenest.planTrip.reports.closure.through', {
      day: new Date(end.getTime() - 1).toLocaleDateString(lang, day),
    })
  }
  return t('greenest.planTrip.reports.closure.until', {
    when: end.toLocaleString(lang, {
      ...day,
      hour: '2-digit',
      minute: '2-digit',
    }),
  })
}

/** "Closed: Baustelle. 2 reports, through Mon 2 Nov. 1 rider says it is open again." */
export function closureText(
  p: ClosureProperties,
  t: TFunction,
  lang: string,
): string {
  const r = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.reports.closure.${key}`, values)
  const parts = [
    `${t(`greenest.planTrip.reports.status.${p.status}`)}${p.note ? `: ${p.note}` : ''}.`,
  ]
  if (p.status !== 'unconfirmed') {
    parts.push(
      `${r('reports', { count: p.reports })}, ${until(p.expires, t, lang)}.`,
    )
  }
  if (p.open_reports) {
    parts.push(r('openReports', { count: p.open_reports }))
  }
  return parts.join(' ')
}

type ReportsCardProps = {
  show: boolean
  onShowChange: (_show: boolean) => void
  /** A closure near the trip's start or end to ask about. */
  near: ClosureFeature | null
  onAnswer: (_segment: string, _stillClosed: boolean) => void
  onSkip: (_segment: string) => void
  /** The thank-you or error line after an answer, here or in a closure's popup. */
  status: string | null
  error: string | null
}

/**
 * Riders' reports (Meldungen) on the map: streets closed for construction and
 * mapping mistakes such as a footway bikes ride on. New ones are reported with
 * "Report a problem" on the map; known closures can be answered here in one tap.
 */
export default function ReportsCard(props: ReportsCardProps) {
  const { t, i18n } = useTranslation()
  const { near, show } = props
  const r = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.reports.${key}`, values)

  return (
    <Card className="flex flex-col gap-3">
      <div className="relative flex items-center gap-1.5">
        <CardTitle>{r('title')}</CardTitle>
        <InfoTip label={r('infoLabel')}>{r('info')}</InfoTip>
      </div>

      {props.status && (
        <p className="text-xs text-leaf-forest" role="status">
          {props.status}
        </p>
      )}

      {near && show && (
        <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-leaf-ink">
          <span>
            {r('near', {
              closure: closureText(near.properties, t, i18n.language),
            })}{' '}
            <strong>{r('askStill')}</strong>
          </span>
          <div className="flex flex-wrap gap-2">
            {(
              [
                [
                  'stillClosed',
                  () => props.onAnswer(near.properties.segment, true),
                ],
                [
                  'openAgain',
                  () => props.onAnswer(near.properties.segment, false),
                ],
                ['dontKnow', () => props.onSkip(near.properties.segment)],
              ] as const
            ).map(([key, onClick]) => (
              <button
                className="rounded-full border border-leaf-sand bg-white px-3 py-1 font-semibold text-leaf-forest hover:bg-leaf-cream"
                key={key}
                onClick={onClick}
                type="button"
              >
                {r(key)}
              </button>
            ))}
          </div>
        </div>
      )}

      <label className="flex cursor-pointer items-center gap-2 text-sm text-leaf-ink/80">
        <input
          checked={show}
          className="h-4 w-4 accent-leaf-forest"
          onChange={e => props.onShowChange(e.target.checked)}
          type="checkbox"
        />
        {r('show')}
      </label>
      {show && (
        <div className="flex flex-col gap-1 text-[11px] text-leaf-muted">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {(['closed', 'reported', 'unconfirmed'] as const).map(status => (
              <span className="inline-flex items-center gap-1.5" key={status}>
                <span
                  aria-hidden
                  className="inline-block h-1.5 w-4 rounded-full"
                  style={{ background: CLOSURE_COLORS[status] }}
                />
                {r(`legend.${status}`)}
              </span>
            ))}
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden
                className="inline-block h-2.5 w-2.5 rounded-full border-2 bg-white"
                style={{ borderColor: MAPPING_COLOR }}
              />
              {r('legend.mapping')}
            </span>
          </div>
          <p>{r('legend.hint')}</p>
          <p>{r('reportHint')}</p>
        </div>
      )}
      {props.error && (
        <p className="text-xs text-red-700" role="alert">
          {props.error}
        </p>
      )}
    </Card>
  )
}
