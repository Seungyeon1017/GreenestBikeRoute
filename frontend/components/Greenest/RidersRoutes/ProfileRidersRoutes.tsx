'use client'

import { Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import {
  deleteCommunityRoute,
  fetchMyCommunityRoutes,
  fetchSavedCommunityRoutes,
  setSaved,
} from '@/services/communityRoutesApi'
import type { CommunityRouteSummary } from '@/types/users'
import { km, rideTime } from './format'
import RouteShape from './RouteShape'

type Which = 'mine' | 'saved'

/**
 * A Profile card with the leisure routes you published (with their status, to
 * delete) or the ones you saved (to remove).
 */
export default function ProfileRidersRoutes({
  token,
  which,
}: {
  token: string
  which: Which
}) {
  const { t } = useTranslation()
  const [routes, setRoutes] = useState<CommunityRouteSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ;(which === 'mine'
      ? fetchMyCommunityRoutes(token)
      : fetchSavedCommunityRoutes(token)
    )
      .then(setRoutes)
      .catch((err: Error) => setError(err.message))
  }, [token, which])

  async function remove(route: CommunityRouteSummary) {
    if (
      which === 'mine' &&
      !window.confirm(t('greenest.ridersRoutes.confirmDelete'))
    ) {
      return
    }
    try {
      await (which === 'mine'
        ? deleteCommunityRoute(token, route.id)
        : setSaved(token, route.id, false))
      setRoutes(prev => prev?.filter(r => r.id !== route.id) ?? null)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const removeLabel = t(
    which === 'mine'
      ? 'greenest.ridersRoutes.delete'
      : 'greenest.ridersRoutes.unsave',
  )

  return (
    <Card className="flex flex-col gap-3">
      <CardTitle>{t(`greenest.profile.ridersRoutes.${which}Title`)}</CardTitle>
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
      {routes === null && !error && (
        <p className="text-sm text-leaf-muted">
          {t('greenest.profile.loading')}
        </p>
      )}
      {routes?.length === 0 && (
        <p className="text-sm text-leaf-muted">
          {t(`greenest.profile.ridersRoutes.${which}Empty`)}{' '}
          <Link
            className="font-medium text-leaf-forest underline"
            href={which === 'mine' ? '/highlights?share=1' : '/highlights'}
          >
            {t(
              which === 'mine'
                ? 'greenest.ridersRoutes.shareYours'
                : 'greenest.nav.highlights',
            )}
          </Link>
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {routes?.map(route => (
          <li
            className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-leaf-sand/70 p-3"
            key={route.id}
          >
            <div className="flex min-w-0 items-center gap-3">
              <RouteShape
                className="h-10 w-10 shrink-0"
                points={route.preview}
              />
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate text-sm font-medium text-leaf-ink">
                  {route.name}
                </span>
                <span className="text-xs text-leaf-muted">
                  {[
                    km(route.length_m),
                    rideTime(route.moving_s),
                    t('greenest.ridersRoutes.hearts', { count: route.hearts }),
                  ].join(' · ')}
                </span>
                {route.status !== 'published' && (
                  <span className="text-xs text-amber-800">
                    {t(`greenest.ridersRoutes.status.${route.status}`)}
                  </span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link
                className="rounded-full bg-leaf-forest px-3 py-1.5 text-xs font-semibold text-leaf-cream hover:bg-leaf-moss"
                href={`/highlights?route=${route.id}`}
              >
                {t('greenest.profile.open')}
              </Link>
              <button
                aria-label={removeLabel}
                className="rounded-full p-1.5 text-leaf-muted hover:bg-red-50 hover:text-red-700"
                onClick={() => remove(route)}
                title={removeLabel}
                type="button"
              >
                <Trash2 aria-hidden className="h-4 w-4" />
              </button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}
