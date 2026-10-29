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
import Dialog from '@/components/Greenest/ui/Dialog'
import RidersRouteCard from './RidersRouteCard'
import RouteDetailDialog from './RouteDetailDialog'
import ShareRouteForm from './ShareRouteForm'

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

/** After logging in, the login page comes back here with the upload popup open. */
const SHARE_HREF = '/highlights?share=1'

/**
 * Highlights' "Routen von Fahrer:innen": leisure routes riders recorded and
 * shared, most hearted first (or newest), filtered by tag. A route opens in a
 * popup with its map; "Eigene Route teilen" opens the GPX upload in a popup.
 * Links open them too: /highlights?route=<id> and /highlights?share=1.
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
  const [openId, setOpenId] = useState<number | null>(null)
  const [sharing, setSharing] = useState(false)
  // Bumped after publishing, to load the list again with the new route.
  const [reload, setReload] = useState(0)

  // Opened from a link: a route (?route=<id>) or the upload (?share=1, after logging in).
  useEffect(() => {
    if (status === 'loading') {
      return
    }
    const params = new URLSearchParams(window.location.search)
    const id = Number(params.get('route'))
    if (id) {
      setOpenId(id)
    } else if (params.get('share') && status === 'authenticated') {
      setSharing(true)
    }
    if (params.has('route') || params.has('share')) {
      window.history.replaceState(null, '', window.location.pathname)
    }
  }, [status])

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
  }, [sort, tag, token, status, reload])

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
    setRoutes(
      prev =>
        prev?.map(r =>
          // The popup's route has its whole line; the list keeps summaries.
          r.id === route.id
            ? {
                ...r,
                hearts: route.hearts,
                hearted: route.hearted,
                saved: route.saved,
              }
            : r,
        ) ?? null,
    )

  function deleted(id: number) {
    setOpenId(null)
    setRoutes(prev => prev?.filter(r => r.id !== id) ?? null)
    setTotal(n => Math.max(n - 1, 0))
  }

  const shareClass =
    'flex shrink-0 items-center gap-2 self-start rounded-full bg-leaf-forest px-4 py-2 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss md:self-auto'

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
        {status === 'authenticated' ? (
          <button
            className={shareClass}
            onClick={() => setSharing(true)}
            type="button"
          >
            <Upload aria-hidden className="h-4 w-4" />
            {t('greenest.ridersRoutes.shareYours')}
          </button>
        ) : (
          <Link
            className={shareClass}
            href={`/login?next=${encodeURIComponent(SHARE_HREF)}`}
          >
            <Upload aria-hidden className="h-4 w-4" />
            {t('greenest.ridersRoutes.loginToShare')}
          </Link>
        )}
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
            <RidersRouteCard
              key={route.id}
              onChange={updated}
              onOpen={() => setOpenId(route.id)}
              route={route}
            />
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

      <RouteDetailDialog
        onChange={updated}
        onClose={() => setOpenId(null)}
        onDeleted={deleted}
        routeId={openId}
        summary={routes?.find(r => r.id === openId)}
      />
      <Dialog
        onClose={() => setSharing(false)}
        open={sharing}
        title={t('greenest.ridersRoutes.upload.title')}
      >
        <ShareRouteForm
          onPublished={route => {
            setSharing(false)
            setReload(n => n + 1)
            setOpenId(route.id)
          }}
        />
      </Dialog>
    </section>
  )
}
