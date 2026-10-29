'use client'

import { Bookmark, Check } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import Card from '@/components/Greenest/ui/Card'
import ShareButton from '@/components/Greenest/ui/ShareButton'
import { tripLink } from '@/lib/shareLink'
import { saveRoute, toSavedOptions } from '@/services/usersApi'
import type {
  LngLat,
  RouteOptions,
  RouteComparison as RouteResult,
} from '@/types/greenest'

type SaveRouteButtonProps = {
  start: LngLat | null
  end: LngLat | null
  startLabel: string
  endLabel: string
  options: RouteOptions
  /** The current route; nothing to save until there is one. */
  result: RouteResult | null
  /** Set when opening a saved route from the profile failed. */
  openError?: string | null
}

type State = 'idle' | 'saving' | 'saved' | 'error'

/**
 * "Save route" and "Share" under the route comparison. Logged out, Save links to
 * the login page and back. Saved routes appear on the Profile tab (the newest 3
 * are kept). Share needs no login: the link carries the trip and its options.
 */
export default function SaveRouteButton({
  start,
  end,
  startLabel,
  endLabel,
  options,
  result,
  openError,
}: SaveRouteButtonProps) {
  const { t } = useTranslation()
  const { status, token } = useAuth()
  const [state, setState] = useState<State>('idle')
  const [error, setError] = useState<string | null>(null)

  // A new route (other points or settings) can be saved again.
  useEffect(() => {
    setState('idle')
    setError(null)
  }, [start, end, options])

  async function save() {
    if (!token || !start || !end || !result) {
      return
    }
    setState('saving')
    try {
      const { properties } = result.route
      await saveRoute(token, {
        start_lon: start[0],
        start_lat: start[1],
        start_label: startLabel || null,
        end_lon: end[0],
        end_lat: end[1],
        end_label: endLabel || null,
        options: toSavedOptions(options),
        length_m: properties.length_m,
        duration_s: Math.round(properties.duration_s),
      })
      setState('saved')
    } catch (err) {
      setError((err as Error).message)
      setState('error')
    }
  }

  return (
    <Card className="flex flex-col gap-2">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
        {status === 'authenticated' ? (
          <button
            className="flex items-center justify-center gap-2 rounded-full bg-leaf-forest px-4 py-2.5 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss disabled:cursor-not-allowed disabled:bg-leaf-sand disabled:text-leaf-muted"
            disabled={!result || state === 'saving' || state === 'saved'}
            onClick={save}
            type="button"
          >
            {state === 'saved' ? (
              <Check aria-hidden className="h-4 w-4" />
            ) : (
              <Bookmark aria-hidden className="h-4 w-4" />
            )}
            {t(`greenest.planTrip.save.${state === 'error' ? 'idle' : state}`)}
          </button>
        ) : (
          <Link
            className="flex items-center justify-center gap-2 rounded-full border border-leaf-sand px-4 py-2.5 text-sm font-medium text-leaf-ink hover:bg-leaf-mint"
            href="/login?next=/plan-trip"
          >
            <Bookmark aria-hidden className="h-4 w-4" />
            {t('greenest.planTrip.save.loginToSave')}
          </Link>
        )}
        <ShareButton
          disabled={!start || !end || !result}
          link={() =>
            start && end
              ? tripLink(start, end, startLabel, endLabel, options)
              : window.location.href
          }
          title={t('greenest.share.tripTitle', {
            from: startLabel,
            to: endLabel,
          })}
        />
      </div>
      <p className="text-[11px] text-leaf-muted">
        {state === 'saved' ? (
          <>
            {t('greenest.planTrip.save.savedHint')}{' '}
            <Link
              className="font-medium text-leaf-forest underline"
              href="/profile"
            >
              {t('greenest.nav.profile')}
            </Link>
          </>
        ) : (
          t('greenest.planTrip.save.hint')
        )}
      </p>
      {(error || openError) && (
        <p className="text-xs text-red-700" role="alert">
          {error ?? openError}
        </p>
      )}
    </Card>
  )
}
