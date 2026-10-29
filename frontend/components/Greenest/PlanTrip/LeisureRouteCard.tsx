'use client'

import { Flag, Navigation, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import { day, km, rideTime } from '@/components/Greenest/RidersRoutes/format'
import HeartSaveButtons from '@/components/Greenest/RidersRoutes/HeartSaveButtons'
import TagList from '@/components/Greenest/RidersRoutes/TagList'
import Card from '@/components/Greenest/ui/Card'
import ShareButton from '@/components/Greenest/ui/ShareButton'
import { communityRouteLink } from '@/lib/shareLink'
import { deleteCommunityRoute, flagRoute } from '@/services/communityRoutesApi'
import type { CommunityRoute } from '@/types/users'
import { LEISURE_COLOR } from './leisureLayers'

type LeisureRouteCardProps = {
  route: CommunityRoute
  /** Plan the trip from your start to where the route begins. */
  onRideThere: () => void
  onClose: () => void
  /** After the author deleted it. */
  onDeleted: () => void
}

/** A riders' leisure route shown on the Plan trip map: what it is, and what you can do with it. */
export default function LeisureRouteCard({
  route,
  onRideThere,
  onClose,
  onDeleted,
}: LeisureRouteCardProps) {
  const { t, i18n } = useTranslation()
  const { status, token } = useAuth()
  const [flagging, setFlagging] = useState(false)
  const [reason, setReason] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function sendFlag() {
    if (!token) {
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
    if (!token || !window.confirm(t('greenest.ridersRoutes.confirmDelete'))) {
      return
    }
    try {
      await deleteCommunityRoute(token, route.id)
      onDeleted()
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <Card
      className="flex flex-col gap-3 border-l-4"
      style={{ borderLeftColor: LEISURE_COLOR }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[11px] font-semibold uppercase tracking-wide text-leaf-muted">
            {t('greenest.ridersRoutes.kicker')}
          </span>
          <h2 className="font-display text-lg font-semibold leading-snug text-leaf-forest">
            {route.name}
          </h2>
          <p className="text-xs text-leaf-muted">
            {[
              route.author
                ? t('greenest.ridersRoutes.by', { name: route.author })
                : t('greenest.ridersRoutes.byRider'),
              t('greenest.ridersRoutes.recordedOn', {
                date: day(route.recorded_on, i18n.language),
              }),
            ].join(' · ')}
          </p>
        </div>
        <button
          aria-label={t('greenest.ridersRoutes.close')}
          className="rounded-full p-1 text-leaf-muted hover:bg-leaf-mint"
          onClick={onClose}
          type="button"
        >
          <X aria-hidden className="h-4 w-4" />
        </button>
      </div>

      {route.status !== 'published' && (
        <p className="rounded-xl bg-amber-50 p-2 text-xs text-amber-900">
          {t(`greenest.ridersRoutes.status.${route.status}`)}
        </p>
      )}

      <p className="text-sm font-medium text-leaf-ink">
        {km(route.length_m)} · {rideTime(route.moving_s)}
      </p>
      <TagList isLoop={route.is_loop} tags={route.tags} />
      {route.description && (
        <p className="whitespace-pre-line text-sm text-leaf-ink">
          {route.description}
        </p>
      )}
      {route.creator && (
        <p className="text-[11px] text-leaf-muted">
          {t('greenest.ridersRoutes.recordedWith', { app: route.creator })}
        </p>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
        <button
          className="flex items-center justify-center gap-2 rounded-full bg-leaf-forest px-4 py-2.5 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss"
          onClick={onRideThere}
          type="button"
        >
          <Navigation aria-hidden className="h-4 w-4" />
          {t('greenest.ridersRoutes.rideThere')}
        </button>
        <ShareButton
          link={() => communityRouteLink(route.id)}
          title={route.name}
        />
      </div>
      <p className="text-[11px] text-leaf-muted">
        {t('greenest.ridersRoutes.rideThereHint')}
      </p>

      {route.status === 'published' && (
        <HeartSaveButtons
          loginNext={`/plan-trip?route=${route.id}`}
          route={route}
        />
      )}

      <div className="flex flex-wrap items-center gap-3 border-t border-leaf-sand/70 pt-2">
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
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </Card>
  )
}
