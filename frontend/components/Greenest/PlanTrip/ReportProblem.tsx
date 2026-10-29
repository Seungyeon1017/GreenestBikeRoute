'use client'

import { Flag, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { LngLat, ReportKind, ReportPick } from '@/types/greenest'

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
  /** Another map mistake: where the rider clicked, until it is sent or cancelled. */
  draft: LngLat | null
  /** A closed street or a footway: the segments or ways picked on the map. */
  picks: ReportPick[]
  onRemovePick: (_key: string) => void
  /** Looking up the street or footway under a click. */
  picking: boolean
  pickError: string | null
  /** Sends the report; resolves to the thank-you line, rejects with the backend's message. */
  onSubmit: (_note: string, _until: string) => Promise<string>
}

/**
 * "Report a problem" at the top right of the map. A map click always plans the
 * route; only after picking what to report here does a click pick a street
 * segment (a closed street), a footway (one bikes ride on) or a spot (another map
 * mistake), and the form for it opens in this panel. Streets and footways can be
 * picked several at a time: one building site often spans several segments.
 */
export default function ReportProblem({
  kind,
  onKindChange,
  draft,
  picks,
  onRemovePick,
  picking,
  pickError,
  onSubmit,
}: ReportProblemProps) {
  const { t, i18n } = useTranslation()
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
  // Ready for the form: a spot for another mistake, at least one street or footway otherwise.
  const ready = kind === 'other' ? draft !== null : picks.length > 0

  function close() {
    setMenu(false)
    setThanks(null)
    onKindChange(null)
  }

  // A different kind starts a fresh form.
  useEffect(() => {
    setNote('')
    setUntilDay('')
    setFormError(null)
  }, [kind])
  useEffect(() => setFormError(null), [draft, picks])

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
          ) : !ready ? (
            <>
              <strong className="text-sm text-leaf-forest">
                {r(`mode.${kind}`)}
              </strong>
              <p>{r(`clickHint.${kind}`)}</p>
              {picking && (
                <p className="text-leaf-muted">{r('pick.looking')}</p>
              )}
              {pickError && (
                <p className="text-red-700" role="alert">
                  {pickError}
                </p>
              )}
            </>
          ) : (
            <form className="flex flex-col gap-2" onSubmit={submit}>
              <strong className="text-sm text-leaf-forest">
                {r(`form.title.${kind}`)}
              </strong>
              {kind !== 'other' && (
                <>
                  <span className="text-leaf-muted">
                    {r(`pick.count.${kind}`, { count: picks.length })}
                  </span>
                  <ul className="flex flex-col gap-1">
                    {picks.map(p => (
                      <li
                        className="flex items-center gap-2 rounded-lg bg-leaf-cream px-2 py-1"
                        key={p.key}
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {p.name ?? r(`pick.unnamed.${kind}`)}
                        </span>
                        {p.status && (
                          <span className="shrink-0 text-[10px] text-amber-800">
                            {r(`status.${p.status}`)}
                          </span>
                        )}
                        <span className="shrink-0 tabular-nums text-leaf-muted">
                          {Math.round(p.length_m).toLocaleString(i18n.language)}{' '}
                          m
                        </span>
                        <button
                          aria-label={r('pick.remove')}
                          className="shrink-0 rounded-full p-0.5 text-leaf-muted hover:bg-white hover:text-leaf-forest"
                          onClick={() => onRemovePick(p.key)}
                          type="button"
                        >
                          <X aria-hidden className="h-3 w-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                  {picking && (
                    <p className="text-leaf-muted">{r('pick.looking')}</p>
                  )}
                  {pickError && (
                    <p className="text-red-700" role="alert">
                      {pickError}
                    </p>
                  )}
                </>
              )}
              <label className="flex flex-col gap-1">
                {r(`form.note.${kind}`)}
                <input
                  autoFocus={kind === 'other'}
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
              <p className="text-leaf-muted">
                {kind === 'other'
                  ? r('form.moveHint')
                  : r(`pick.addHint.${kind}`)}
              </p>
              {formError && (
                <p className="text-red-700" role="alert">
                  {formError}
                </p>
              )}
              <button
                className="self-start rounded-full bg-leaf-forest px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                disabled={sending || picking}
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
