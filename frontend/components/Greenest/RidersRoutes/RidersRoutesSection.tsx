'use client'

import { cx } from 'class-variance-authority'
import { Upload } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import Card from '@/components/Greenest/ui/Card'
import { fetchCommunityRoutes } from '@/services/communityRoutesApi'
import {
  type CommunityRouteSort,
  type CommunityRouteSummary,
  ROUTE_TAGS,
  type RouteTag,
} from '@/types/users'
import RidersRouteCard from './RidersRouteCard'

const PAGE = 8

const CHIP =
  'rounded-full border px-3 py-1 text-xs font-medium transition-colors'
const chip = (on: boolean) =>
  cx(
    CHIP,
    on
      ? 'border-leaf-forest bg-leaf-forest text-leaf-cream'
      : 'border-leaf-sand bg-white text-leaf-ink hover:bg-leaf-mint',
  )

/**
 * Highlights' "Routen von Fahrer:innen": leisure routes riders recorded and
 * shared, most hearted first (or newest), filtered by tag, with a way to share
 * your own.
 */
export default function RidersRoutesSection() {
  const { t } = useTranslation()
  const { status, token } = useAuth()
  const [sort, setSort] = useState<CommunityRouteSort>('hearts')
  const [tag, setTag] = useState<RouteTag | null>(null)
  const [routes, setRoutes] = useState<CommunityRouteSummary[] | null>(null)
  const [total, setTotal] = useState(0)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // First page again when the sort, the tag or the login changes.
  useEffect(() => {
    if (status === 'loading') {
      return
    }
    let current = true
    setRoutes(null)
    setError(null)
    fetchCommunityRoutes(token, { sort, tag, limit: PAGE, offset: 0 })
      .then(list => {
        if (current) {
          setRoutes(list.routes)
          setTotal(list.total)
        }
      })
      .catch((err: Error) => current && setError(err.message))
    return () => {
      current = false
    }
  }, [sort, tag, token, status])

  async function loadMore() {
    setLoadingMore(true)
    try {
      const list = await fetchCommunityRoutes(token, {
        sort,
        tag,
        limit: PAGE,
        offset: routes?.length ?? 0,
      })
      setRoutes(prev => [...(prev ?? []), ...list.routes])
      setTotal(list.total)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoadingMore(false)
    }
  }

  const updated = (route: CommunityRouteSummary) =>
    setRoutes(prev => prev?.map(r => (r.id === route.id ? route : r)) ?? null)

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div className="space-y-1.5">
          <h2 className="font-display text-2xl font-medium tracking-tight text-leaf-forest md:text-3xl">
            {t('greenest.ridersRoutes.title')}
          </h2>
          <p className="text-sm leading-relaxed text-leaf-muted">
            {t('greenest.ridersRoutes.text')}
          </p>
        </div>
        <Link
          className="flex shrink-0 items-center gap-2 self-start rounded-full bg-leaf-forest px-4 py-2 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss md:self-auto"
          href={
            status === 'authenticated'
              ? '/plan-trip?contribute=1'
              : `/login?next=${encodeURIComponent('/plan-trip?contribute=1')}`
          }
        >
          <Upload aria-hidden className="h-4 w-4" />
          {t('greenest.ridersRoutes.shareYours')}
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div
          aria-label={t('greenest.ridersRoutes.sortLabel')}
          className="flex gap-1"
          role="group"
        >
          {(['hearts', 'newest'] as const).map(value => (
            <button
              aria-pressed={sort === value}
              className={chip(sort === value)}
              key={value}
              onClick={() => setSort(value)}
              type="button"
            >
              {t(`greenest.ridersRoutes.sort.${value}`)}
            </button>
          ))}
        </div>
        <span aria-hidden className="mx-1 h-5 w-px bg-leaf-sand" />
        <div
          aria-label={t('greenest.ridersRoutes.tagLabel')}
          className="flex flex-wrap gap-1"
          role="group"
        >
          <button
            aria-pressed={tag === null}
            className={chip(tag === null)}
            onClick={() => setTag(null)}
            type="button"
          >
            {t('greenest.ridersRoutes.allTags')}
          </button>
          {ROUTE_TAGS.map(value => (
            <button
              aria-pressed={tag === value}
              className={chip(tag === value)}
              key={value}
              onClick={() =>
                setTag(current => (current === value ? null : value))
              }
              type="button"
            >
              {t(`greenest.ridersRoutes.tags.${value}`)}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <p className="text-sm text-red-700" role="alert">
          {error}
        </p>
      )}
      {routes === null && !error && (
        <p className="text-sm text-leaf-muted">
          {t('greenest.ridersRoutes.loading')}
        </p>
      )}
      {routes?.length === 0 && (
        <Card className="bg-leaf-cream text-sm text-leaf-muted">
          {t(
            tag
              ? 'greenest.ridersRoutes.emptyTag'
              : 'greenest.ridersRoutes.empty',
          )}
        </Card>
      )}
      {routes && routes.length > 0 && (
        <div className="grid gap-4 xs:grid-cols-2 lg:grid-cols-4">
          {routes.map(route => (
            <RidersRouteCard key={route.id} onChange={updated} route={route} />
          ))}
        </div>
      )}
      {routes && routes.length < total && (
        <button
          className="self-center rounded-full border border-leaf-sand px-4 py-2 text-sm font-medium text-leaf-ink hover:bg-leaf-mint disabled:opacity-60"
          disabled={loadingMore}
          onClick={loadMore}
          type="button"
        >
          {t('greenest.ridersRoutes.more')}
        </button>
      )}
    </section>
  )
}
