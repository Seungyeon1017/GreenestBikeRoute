'use client'

import { Flag, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { LngLat, ReportKind } from '@/types/greenest'

/** The backend keeps a closure report through its `until` day, at most 30 days ahead. */
const MAX_UNTIL_DAYS = 30

/** How long the thank-you stays before the panel closes by itself. */
const THANKS_MS = 6000

const KINDS: ReportKind[] = ['closure', 'rideable', 'other']

/** A local date as YYYY-MM-DD, `days` from today. */
function dayFromToday(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

type ReportProblemProps = {
  /** What is being reported; null while the map plans the route. */
  kind: ReportKind | null
  onKindChange: (_kind: ReportKind | null) => void
  /** Where the rider clicked the map to report, until it is sent or cancelled. */
  draft: LngLat | null
  /** Sends the draft; resolves to the thank-you line, rejects with the backend's message. */
  onSubmit: (_note: string, _until: string) => Promise<string>
}

const BUTTON =
  'rounded-full px-4 py-1.5 text-xs font-semibold disabled:opacity-50'

/**
 * "Report a problem" at the top right of the map. A map click always plans the
 * route; only after picking what to report here (a closed street, a footway bikes
 * ride on, another map mistake) does the next click mark the spot, and the form
 * for it opens in this panel.
 */
export default function ReportProblem({
  kind,
  onKindChange,
  draft,
  onSubmit,
}: ReportProblemProps) {
  const { t } = useTranslation()
  const r = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.reports.${key}`, values)

  // The menu of what to report is open (before a kind is picked).
  const [menu, setMenu] = useState(false)
  const [note, setNote] = useState('')
  const [untilDay, setUntilDay] = useState('')
  const [sending, setSending] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [thanks, setThanks] = useState<string | null>(null)
  const open = menu || kind !== null || thanks !== null

  function close() {
    setMenu(false)
    setThanks(null)
    onKindChange(null)
  }

  // A different kind or spot starts a fresh form.
  useEffect(() => {
    setNote('')
    setUntilDay('')
    setFormError(null)
  }, [kind])
  useEffect(() => setFormError(null), [draft])

  // The thank-you closes the panel after a while.
  useEffect(() => {
    if (!thanks) {
      return
    }
    const timer = setTimeout(() => setThanks(null), THANKS_MS)
    return () => clearTimeout(timer)
  }, [thanks])

  // Esc goes back to planning the route.
  useEffect(() => {
    if (!open) {
      return
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        close()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  async function submit(e: FormEvent) {
    e.preventDefault()
    setSending(true)
    setFormError(null)
    try {
      const message = await onSubmit(note.trim(), untilDay)
      setMenu(false)
      onKindChange(null)
      setThanks(message)
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    // Left of MapLibre's zoom buttons, which sit in the top right corner.
    <div className="absolute right-12 top-2.5 z-10 flex w-[min(18rem,calc(100%-4rem))] flex-col items-end gap-2">
      <button
        aria-expanded={open}
        className="inline-flex items-center gap-1.5 rounded-full border border-leaf-sand bg-white px-3 py-1.5 text-xs font-semibold text-leaf-forest shadow-soft hover:bg-leaf-cream"
        onClick={() => (open ? close() : setMenu(true))}
        type="button"
      >
        {open ? (
          <X aria-hidden className="h-3.5 w-3.5" />
        ) : (
          <Flag aria-hidden className="h-3.5 w-3.5" />
        )}
        {thanks ? r('form.close') : open ? r('form.cancel') : r('button')}
      </button>

      {open && (
        <div className="flex max-h-[min(28rem,calc(100vh-8rem))] w-full flex-col gap-2 overflow-y-auto rounded-2xl border border-leaf-sand bg-white p-3 text-xs text-leaf-ink shadow-soft">
          {thanks ? (
            <p className="text-leaf-forest" role="status">
              {thanks}
            </p>
          ) : !kind ? (
            <>
              <strong className="text-sm text-leaf-forest">
                {r('chooseLabel')}
              </strong>
              {KINDS.map(k => (
                <button
                  className="rounded-xl border border-leaf-sand px-3 py-2 text-left text-sm hover:bg-leaf-cream"
                  key={k}
                  onClick={() => onKindChange(k)}
                  type="button"
                >
                  {r(`mode.${k}`)}
                </button>
              ))}
            </>
          ) : !draft ? (
            <>
              <strong className="text-sm text-leaf-forest">
                {r(`mode.${kind}`)}
              </strong>
              <p>{r(`clickHint.${kind}`)}</p>
            </>
          ) : (
            <form className="flex flex-col gap-2" onSubmit={submit}>
              <strong className="text-sm text-leaf-forest">
                {r(`form.title.${kind}`)}
              </strong>
              <label className="flex flex-col gap-1">
                {r(`form.note.${kind}`)}
                <input
                  autoFocus
                  className="rounded-lg border border-leaf-sand bg-white px-2 py-1 text-sm"
                  maxLength={500}
                  onChange={e => setNote(e.target.value)}
                  placeholder={r(`form.placeholder.${kind}`)}
                  required={kind === 'other'}
                  value={note}
                />
              </label>
              {kind === 'closure' && (
                <label className="flex flex-col gap-1">
                  {r('form.until')}
                  <input
                    className="rounded-lg border border-leaf-sand bg-white px-2 py-1 text-sm"
                    max={dayFromToday(MAX_UNTIL_DAYS)}
                    min={dayFromToday(0)}
                    onChange={e => setUntilDay(e.target.value)}
                    type="date"
                    value={untilDay}
                  />
                  <span className="text-leaf-muted">{r('form.untilHint')}</span>
                </label>
              )}
              <p className="text-leaf-muted">{r('form.moveHint')}</p>
              {formError && (
                <p className="text-red-700" role="alert">
                  {formError}
                </p>
              )}
              <button
                className={`${BUTTON} self-start bg-leaf-forest text-white`}
                disabled={sending}
                type="submit"
              >
                {sending ? r('form.sending') : r('form.send')}
              </button>
            </form>
          )}
        </div>
      )}
    </div>
  )
}
