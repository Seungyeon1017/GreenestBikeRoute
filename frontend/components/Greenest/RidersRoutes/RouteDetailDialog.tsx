'use client'

import { Flag, Navigation, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import Dialog from '@/components/Greenest/ui/Dialog'
import ShareButton from '@/components/Greenest/ui/ShareButton'
import { communityRouteLink } from '@/lib/shareLink'
import {
  deleteCommunityRoute,
  fetchCommunityRoute,
  flagRoute,
} from '@/services/communityRoutesApi'
import type { CommunityRoute, CommunityRouteSummary } from '@/types/users'
import { day, km, rideTime } from './format'
import HeartSaveButtons from './HeartSaveButtons'
import RouteMap from './RouteMap'
import TagList from './TagList'

type RouteDetailDialogProps = {
  /** The route to show, or null when the popup is closed. */
  routeId: number | null
  /** What the list already knows, so the title shows while the line loads. */
  summary?: CommunityRouteSummary
  onClose: () => void
  /** Hearted or saved, to update the list. */
  onChange: (_route: CommunityRouteSummary) => void
  /** The author deleted it. */
  onDeleted: (_id: number) => void
}

/** Plan trip with the route's start as the destination (Highlights' place cards send the same). */
function rideThereHref(route: CommunityRoute) {
  const [lng, lat] = route.coordinates[0]
  const query = new URLSearchParams({ to: `${lng},${lat}`, name: route.name })
  return `/plan-trip?${query}`
}

/**
 * A riders' leisure route in a popup on Highlights: the line on a map, what it
 * is, heart / save / share, flag (or delete your own), and Ride there.
 */
export default function RouteDetailDialog({
  routeId,
  summary,
  onClose,
  onChange,
  onDeleted,
}: RouteDetailDialogProps) {
  const { t, i18n } = useTranslation()
  const { status, token } = useAuth()
  const [route, setRoute] = useState<CommunityRoute | null>(null)
  const [flagging, setFlagging] = useState(false)
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setRoute(null)
    setFlagging(false)
    setReason('')
    setMessage(null)
    setError(null)
    if (routeId === null || status === 'loading') {
      return
    }
    let current = true
    fetchCommunityRoute(token, routeId)
      .then(r => current && setRoute(r))
      .catch(
        (err: Error & { status?: number }) =>
          current &&
          setError(
            err.status === 404
              ? t('greenest.ridersRoutes.notFound')
              : err.message,
          ),
      )
    return () => {
      current = false
    }
  }, [routeId, token, status, t])

  async function sendFlag() {
    if (!token || !route) {
      return
    }
    setError(null)
    try {
      await flagRoute(token, route.id, reason)
      setFlagging(false)
      setMessage(t('greenest.ridersRoutes.flagThanks'))
    } catch (err) {
      setError((err as Error).message)
    }
  }

  async function remove() {
    if (
      !token ||
      !route ||
      !window.confirm(t('greenest.ridersRoutes.confirmDelete'))
    ) {
      return
    }
    try {
      await deleteCommunityRoute(token, route.id)
      onDeleted(route.id)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const shown = route ?? summary

  return (
    <Dialog
      kicker={t('greenest.ridersRoutes.kicker')}
      onClose={onClose}
      open={routeId !== null}
      title={shown?.name ?? t('greenest.ridersRoutes.loadingRoute')}
    >
      <RouteMap
        ariaLabel={t('greenest.ridersRoutes.mapLabel', {
          name: shown?.name ?? '',
        })}
        coordinates={route?.coordinates ?? null}
      />

      {shown && (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-leaf-muted">
            {[
              shown.author
                ? t('greenest.ridersRoutes.by', { name: shown.author })
                : t('greenest.ridersRoutes.byRider'),
              t('greenest.ridersRoutes.recordedOn', {
                date: day(shown.recorded_on, i18n.language),
              }),
            ].join(' · ')}
          </p>
          {shown.status !== 'published' && (
            <p className="rounded-xl bg-amber-50 p-2 text-xs text-amber-900">
              {t(`greenest.ridersRoutes.status.${shown.status}`)}
            </p>
          )}
          <p className="text-sm font-medium text-leaf-ink">
            {km(shown.length_m)} · {rideTime(shown.moving_s)}
          </p>
          <TagList isLoop={shown.is_loop} tags={shown.tags} />
          {shown.description && (
            <p className="whitespace-pre-line text-sm text-leaf-ink">
              {shown.description}
            </p>
          )}
          {shown.creator && (
            <p className="text-[11px] text-leaf-muted">
              {t('greenest.ridersRoutes.recordedWith', { app: shown.creator })}
            </p>
          )}
        </div>
      )}

      {route && (
        <>
          <div className="sm:grid-cols-[minmax(0,1fr)_auto] grid gap-2">
            <Link
              className="flex items-center justify-center gap-2 rounded-full bg-leaf-forest px-4 py-2.5 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss"
              href={rideThereHref(route)}
            >
              <Navigation aria-hidden className="h-4 w-4" />
              {t('greenest.ridersRoutes.rideThere')}
            </Link>
            <ShareButton
              link={() => communityRouteLink(route.id)}
              title={route.name}
            />
          </div>
          <p className="-mt-2 text-[11px] text-leaf-muted">
            {t('greenest.ridersRoutes.rideThereHint')}
          </p>

          {route.status === 'published' && (
            <HeartSaveButtons
              loginNext={`/highlights?route=${route.id}`}
              onChange={onChange}
              route={route}
            />
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-leaf-sand/70 pt-3">
            {route.mine ? (
              <button
                className="flex items-center gap-1 text-xs text-leaf-muted hover:text-red-700"
                onClick={remove}
                type="button"
              >
                <Trash2 aria-hidden className="h-3.5 w-3.5" />
                {t('greenest.ridersRoutes.delete')}
              </button>
            ) : (
              status === 'authenticated' &&
              !message && (
                <button
                  className="flex items-center gap-1 text-xs text-leaf-muted hover:text-red-700"
                  onClick={() => setFlagging(on => !on)}
                  type="button"
                >
                  <Flag aria-hidden className="h-3.5 w-3.5" />
                  {t('greenest.ridersRoutes.flag')}
                </button>
              )
            )}
            {message && <p className="text-xs text-leaf-moss">{message}</p>}
          </div>
          {flagging && (
            <div className="flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-xs text-leaf-muted">
                {t('greenest.ridersRoutes.flagReason')}
                <textarea
                  className="rounded-lg border border-leaf-sand p-2 text-sm text-leaf-ink"
                  maxLength={300}
                  onChange={e => setReason(e.target.value)}
                  rows={2}
                  value={reason}
                />
              </label>
              <button
                className="self-start rounded-full bg-red-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-800"
                onClick={sendFlag}
                type="button"
              >
                {t('greenest.ridersRoutes.flagSend')}
              </button>
            </div>
          )}
        </>
      )}
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </Dialog>
  )
}
