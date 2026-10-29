'use client'

import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
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

/**
 * "Closed. 2 reports, through Mon 2 Nov. 1 rider says it is open again." The
 * reporter's note goes on its own labelled line (see reportLayers noteLine).
 */
export function closureText(
  p: ClosureProperties,
  t: TFunction,
  lang: string,
): string {
  const r = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.reports.closure.${key}`, values)
  const parts = [`${t(`greenest.planTrip.reports.status.${p.status}`)}.`]
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

type ReportsNoticeProps = {
  /** A closure near the trip's start or end to ask about. */
  near: ClosureFeature | null
  onAnswer: (_segment: string, _stillClosed: boolean) => void
  onSkip: (_segment: string) => void
  /** The thank-you or error line after an answer, here or in a closure's popup. */
  status: string | null
  error: string | null
}

/**
 * On the map beside the Layers button: a known closure near the trip, answered
 * in one tap, and the line that follows an answer. Nothing when there is neither.
 */
export function ReportsNotice({
  near,
  onAnswer,
  onSkip,
  status,
  error,
}: ReportsNoticeProps) {
  const { t, i18n } = useTranslation()
  const r = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.reports.${key}`, values)

  if (!near && !status && !error) {
    return null
  }
  return (
    <div className="pointer-events-auto flex w-72 flex-col gap-2 rounded-2xl border border-leaf-sand bg-white p-3 text-xs text-leaf-ink shadow-soft">
      {status && (
        <p className="text-leaf-forest" role="status">
          {status}
        </p>
      )}
      {near && (
        <div className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-2.5">
          <span>
            {r('near', {
              closure: closureText(near.properties, t, i18n.language),
            })}{' '}
            <strong>{r('askStill')}</strong>
          </span>
          {near.properties.note && (
            <span className="text-leaf-muted">
              <span className="font-semibold">{r('noteLabel')}:</span>{' '}
              {near.properties.note}
            </span>
          )}
          <div className="flex flex-wrap gap-2">
            {(
              [
                ['stillClosed', () => onAnswer(near.properties.segment, true)],
                ['openAgain', () => onAnswer(near.properties.segment, false)],
                ['dontKnow', () => onSkip(near.properties.segment)],
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
      {error && (
        <p className="text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

/**
 * Riders' reports (Meldungen) on the map: streets closed for construction and
 * mapping mistakes such as a footway bikes ride on. The colours, in the Layers
 * panel; new ones are reported with "Report a problem" on the map.
 */
export default function ReportsLegend() {
  const { t } = useTranslation()
  const r = (key: string) => t(`greenest.planTrip.reports.${key}`)

  return (
    <div className="relative flex flex-col gap-1.5 text-[11px] text-leaf-muted">
      <div className="flex items-center gap-1.5">
        <strong className="text-xs text-leaf-forest">{r('title')}</strong>
        <InfoTip above label={r('infoLabel')}>
          {r('info')}
          <span className="mt-1 block">{r('legend.hint')}</span>
          <span className="mt-1 block">{r('reportHint')}</span>
        </InfoTip>
      </div>
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
    </div>
  )
}
