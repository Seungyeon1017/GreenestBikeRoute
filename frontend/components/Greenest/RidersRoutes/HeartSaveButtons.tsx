'use client'

import { cx } from 'class-variance-authority'
import { Bookmark, BookmarkCheck, Heart } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import { setHeart, setSaved } from '@/services/communityRoutesApi'
import type { CommunityRouteSummary } from '@/types/users'

type HeartSaveButtonsProps = {
  route: CommunityRouteSummary
  /** Where the login page sends the rider back to. */
  loginNext: string
  /** After a change, e.g. to update a list. */
  onChange?: (_route: CommunityRouteSummary) => void
  className?: string
}

const BUTTON =
  'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60'

/**
 * Heart (counts towards "Beliebteste") and Save (to the Profile tab). Logged
 * out, they link to the login page. Your own route can't be hearted.
 */
export default function HeartSaveButtons({
  route,
  loginNext,
  onChange,
  className,
}: HeartSaveButtonsProps) {
  const { t } = useTranslation()
  const { status, token } = useAuth()
  const [current, setCurrent] = useState(route)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => setCurrent(route), [route])

  async function toggle(what: 'heart' | 'save') {
    if (!token) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      let next: CommunityRouteSummary
      if (what === 'heart') {
        const state = await setHeart(token, current.id, !current.hearted)
        next = { ...current, ...state }
      } else {
        await setSaved(token, current.id, !current.saved)
        next = { ...current, saved: !current.saved }
      }
      setCurrent(next)
      onChange?.(next)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const hearts = t('greenest.ridersRoutes.hearts', { count: current.hearts })

  if (status !== 'authenticated') {
    return (
      <div className={cx('flex flex-wrap items-center gap-2', className)}>
        <span className="flex items-center gap-1 text-xs text-leaf-muted">
          <Heart aria-hidden className="h-3.5 w-3.5" />
          {hearts}
        </span>
        <Link
          className="text-xs font-medium text-leaf-moss underline hover:text-leaf-forest"
          href={`/login?next=${encodeURIComponent(loginNext)}`}
        >
          {t('greenest.ridersRoutes.loginToHeart')}
        </Link>
      </div>
    )
  }

  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          aria-pressed={current.hearted}
          className={cx(
            BUTTON,
            current.hearted
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-leaf-sand text-leaf-ink hover:bg-leaf-mint',
          )}
          disabled={busy || current.mine}
          onClick={() => toggle('heart')}
          title={
            current.mine
              ? t('greenest.ridersRoutes.ownRoute')
              : t('greenest.ridersRoutes.heart')
          }
          type="button"
        >
          <Heart
            aria-hidden
            className={cx('h-3.5 w-3.5', current.hearted && 'fill-current')}
          />
          {hearts}
        </button>
        <button
          aria-pressed={current.saved}
          className={cx(
            BUTTON,
            current.saved
              ? 'border-leaf-moss bg-leaf-mint text-leaf-forest'
              : 'border-leaf-sand text-leaf-ink hover:bg-leaf-mint',
          )}
          disabled={busy}
          onClick={() => toggle('save')}
          type="button"
        >
          {current.saved ? (
            <BookmarkCheck aria-hidden className="h-3.5 w-3.5" />
          ) : (
            <Bookmark aria-hidden className="h-3.5 w-3.5" />
          )}
          {t(
            current.saved
              ? 'greenest.ridersRoutes.saved'
              : 'greenest.ridersRoutes.save',
          )}
        </button>
      </div>
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
