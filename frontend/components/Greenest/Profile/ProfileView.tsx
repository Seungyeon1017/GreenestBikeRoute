'use client'

import { MapPin, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import ProfileRidersRoutes from '@/components/Greenest/RidersRoutes/ProfileRidersRoutes'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import { deleteSavedRoute, fetchSavedRoutes } from '@/services/usersApi'
import type { SavedRoute } from '@/types/users'

/** "Rathaus Heilbronn", or the coordinates when the point was set by a map click. */
function pointName(label: string | null, lon: number, lat: number): string {
  return label || `${lat.toFixed(4)}, ${lon.toFixed(4)}`
}

/** The logged-in user's account and their saved routes (the backend keeps the newest 3). */
export default function ProfileView() {
  const { t, i18n } = useTranslation()
  const { status, user, token, logOut } = useAuth()
  const [routes, setRoutes] = useState<SavedRoute[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      return
    }
    fetchSavedRoutes(token)
      .then(setRoutes)
      .catch((err: Error) => setError(err.message))
  }, [token])

  async function remove(id: number) {
    if (!token) {
      return
    }
    try {
      await deleteSavedRoute(token, id)
      setRoutes(prev => prev?.filter(r => r.id !== id) ?? null)
    } catch (err) {
      setError((err as Error).message)
    }
  }

  const date = (iso: string) =>
    new Date(iso).toLocaleDateString(i18n.language, { dateStyle: 'medium' })

  if (status === 'loading') {
    return (
      <p className="px-8 py-8 text-sm text-leaf-muted">
        {t('greenest.profile.loading')}
      </p>
    )
  }

  if (status === 'anonymous' || !user) {
    return (
      <div className="mx-auto flex w-full max-w-xl flex-col gap-4 px-4 py-8">
        <PageIntro
          subtitle={t('greenest.profile.loggedOutText')}
          title={t('greenest.profile.title')}
        />
        <Link
          className="self-start rounded-full bg-leaf-forest px-4 py-2 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss"
          href="/login?next=/profile"
        >
          {t('greenest.auth.loginTab')}
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6 md:px-8">
      <PageIntro
        subtitle={t('greenest.profile.subtitle')}
        title={user.display_name ?? t('greenest.profile.title')}
      />

      <Card className="flex flex-col gap-3">
        <CardTitle>{t('greenest.profile.account')}</CardTitle>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-leaf-muted">{t('greenest.auth.email')}</dt>
          <dd className="text-leaf-ink">{user.email}</dd>
          <dt className="text-leaf-muted">
            {t('greenest.profile.memberSince')}
          </dt>
          <dd className="text-leaf-ink">{date(user.created_at)}</dd>
        </dl>
        <button
          className="self-start rounded-full border border-leaf-sand px-4 py-1.5 text-sm text-leaf-ink hover:bg-leaf-cream"
          onClick={logOut}
          type="button"
        >
          {t('greenest.profile.logOut')}
        </button>
      </Card>

      <Card className="flex flex-col gap-3">
        <CardTitle>{t('greenest.profile.savedRoutes')}</CardTitle>
        <p className="text-xs text-leaf-muted">
          {t('greenest.profile.keepsNewest')}
        </p>

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
            {t('greenest.profile.noRoutes')}{' '}
            <Link
              className="font-medium text-leaf-forest underline"
              href="/plan-trip"
            >
              {t('greenest.nav.planTrip')}
            </Link>
          </p>
        )}

        <ul className="flex flex-col gap-2">
          {routes?.map(route => (
            <li
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-leaf-sand/70 p-3"
              key={route.id}
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="flex items-center gap-1.5 text-sm font-medium text-leaf-ink">
                  <MapPin
                    aria-hidden
                    className="h-4 w-4 shrink-0 text-leaf-moss"
                  />
                  <span className="truncate">
                    {pointName(
                      route.start_label,
                      route.start_lon,
                      route.start_lat,
                    )}{' '}
                    → {pointName(route.end_label, route.end_lon, route.end_lat)}
                  </span>
                </span>
                <span className="text-xs text-leaf-muted">
                  {[
                    route.length_m != null &&
                      `${(route.length_m / 1000).toFixed(1)} km`,
                    route.duration_s != null &&
                      `${Math.round(route.duration_s / 60)} min`,
                    t('greenest.profile.savedOn', {
                      date: date(route.created_at),
                    }),
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Link
                  className="rounded-full bg-leaf-forest px-3 py-1.5 text-xs font-semibold text-leaf-cream hover:bg-leaf-moss"
                  href={`/plan-trip?saved=${route.id}`}
                >
                  {t('greenest.profile.open')}
                </Link>
                <button
                  aria-label={t('greenest.profile.delete')}
                  className="rounded-full p-1.5 text-leaf-muted hover:bg-red-50 hover:text-red-700"
                  onClick={() => remove(route.id)}
                  title={t('greenest.profile.delete')}
                  type="button"
                >
                  <Trash2 aria-hidden className="h-4 w-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {token && (
        <>
          <ProfileRidersRoutes token={token} which="mine" />
          <ProfileRidersRoutes token={token} which="saved" />
        </>
      )}
    </div>
  )
}
