'use client'

import { cx } from 'class-variance-authority'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/components/Greenest/Auth/AuthProvider'
import { previewTrack, publishRoute } from '@/services/communityRoutesApi'
import type { GreenestApiError } from '@/services/greenestApi'
import {
  type CommunityRoute,
  ROUTE_TAGS,
  type RouteTag,
  type TrackPreview,
} from '@/types/users'
import { day, km, rideTime } from './format'
import RouteMap from './RouteMap'

const MAX_TAGS = 4
/** Apps whose export steps the form explains (keys under ridersRoutes.upload.apps). */
const APPS = ['komoot', 'strava', 'garmin', 'osmand'] as const

/**
 * "Share your own route", in the Highlights popup: upload a ride recorded with
 * another app (GPX), see it on the map, give it a name, a description and
 * tags, and publish it for everyone. The section only opens it when logged in.
 */
export default function ShareRouteForm({
  onPublished,
}: {
  /** The route is published: show it. */
  onPublished: (_route: CommunityRoute) => void
}) {
  const { t, i18n } = useTranslation()
  const { token } = useAuth()
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<TrackPreview | null>(null)
  const [checking, setChecking] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState<RouteTag[]>([])
  const [publishing, setPublishing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function apiError(err: unknown) {
    const { code, message } = err as GreenestApiError
    return code
      ? t(`greenest.ridersRoutes.upload.errors.${code}`, {
          defaultValue: message,
        })
      : message
  }

  function reset() {
    setFile(null)
    setPreview(null)
    setName('')
    setDescription('')
    setTags([])
    setError(null)
  }

  async function pick(picked: File | undefined) {
    reset()
    if (!picked || !token) {
      return
    }
    setFile(picked)
    setChecking(true)
    try {
      const track = await previewTrack(token, picked)
      setPreview(track)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setChecking(false)
    }
  }

  function toggleTag(tag: RouteTag) {
    setTags(current =>
      current.includes(tag)
        ? current.filter(x => x !== tag)
        : current.length < MAX_TAGS
          ? [...current, tag]
          : current,
    )
  }

  async function publish() {
    if (!token || !file) {
      return
    }
    setPublishing(true)
    setError(null)
    try {
      const route = await publishRoute(token, file, {
        name: name.trim(),
        description: description.trim(),
        tags,
      })
      onPublished(route)
    } catch (err) {
      setError(apiError(err))
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-leaf-muted">
        {t('greenest.ridersRoutes.upload.intro')}
      </p>
      <RouteMap
        ariaLabel={t('greenest.ridersRoutes.upload.mapLabel')}
        coordinates={preview?.coordinates ?? null}
        draft
      />
      <details className="rounded-xl bg-leaf-cream p-3 text-xs text-leaf-ink">
        <summary className="cursor-pointer font-medium">
          {t('greenest.ridersRoutes.upload.howTo')}
        </summary>
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-4">
          {APPS.map(app => (
            <li key={app}>{t(`greenest.ridersRoutes.upload.apps.${app}`)}</li>
          ))}
        </ul>
        <p className="mt-2 text-leaf-muted">
          {t('greenest.ridersRoutes.upload.rules')}
        </p>
      </details>

      {/* Our own button instead of the browser's "Choose File / No file chosen",
              which follows the browser's language, not the page's. */}
      <div className="flex flex-col gap-1 text-xs font-medium text-leaf-ink">
        {t('greenest.ridersRoutes.upload.file')}
        <div className="flex min-w-0 items-center gap-3">
          <label
            className={cx(
              'shrink-0 rounded-full bg-leaf-mint px-3 py-1.5 text-xs font-medium text-leaf-forest focus-within:ring-2 focus-within:ring-leaf-moss',
              checking || publishing
                ? 'cursor-not-allowed opacity-60'
                : 'cursor-pointer hover:bg-leaf-sand',
            )}
          >
            {t('greenest.ridersRoutes.upload.chooseFile')}
            <input
              accept=".gpx,application/gpx+xml"
              className="sr-only"
              disabled={checking || publishing}
              onChange={e => {
                pick(e.target.files?.[0])
                // Lets the same file be picked again after a fix in another app.
                e.target.value = ''
              }}
              type="file"
            />
          </label>
          <span className="truncate font-normal text-leaf-muted">
            {file?.name ?? t('greenest.ridersRoutes.upload.noFile')}
          </span>
        </div>
      </div>
      {checking && (
        <p className="text-xs text-leaf-muted">
          {t('greenest.ridersRoutes.upload.checking')}
        </p>
      )}

      {preview && (
        <>
          <p className="rounded-xl bg-leaf-mint p-2 text-xs text-leaf-forest">
            {[
              km(preview.length_m),
              rideTime(preview.moving_s),
              day(preview.recorded_on, i18n.language),
              preview.is_loop && t('greenest.ridersRoutes.loop'),
            ]
              .filter(Boolean)
              .join(' · ')}
            <br />
            {t('greenest.ridersRoutes.upload.trimmed')}
          </p>
          <label className="flex flex-col gap-1 text-xs font-medium text-leaf-ink">
            {t('greenest.ridersRoutes.upload.name')}
            <input
              className="rounded-lg border border-leaf-sand px-2 py-1.5 text-sm font-normal"
              maxLength={80}
              onChange={e => setName(e.target.value)}
              placeholder={t('greenest.ridersRoutes.upload.namePlaceholder')}
              value={name}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-leaf-ink">
            {t('greenest.ridersRoutes.upload.description')}
            <textarea
              className="rounded-lg border border-leaf-sand px-2 py-1.5 text-sm font-normal"
              maxLength={500}
              onChange={e => setDescription(e.target.value)}
              placeholder={t(
                'greenest.ridersRoutes.upload.descriptionPlaceholder',
              )}
              rows={3}
              value={description}
            />
          </label>
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1 text-xs font-medium text-leaf-ink">
              {t('greenest.ridersRoutes.upload.tags', { count: MAX_TAGS })}
            </legend>
            <div className="flex flex-wrap gap-1.5">
              {ROUTE_TAGS.map(tag => (
                <button
                  aria-pressed={tags.includes(tag)}
                  className={cx(
                    'rounded-full border px-2.5 py-1 text-xs',
                    tags.includes(tag)
                      ? 'border-leaf-moss bg-leaf-mint text-leaf-forest'
                      : 'border-leaf-sand text-leaf-ink hover:bg-leaf-cream',
                  )}
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  type="button"
                >
                  {t(`greenest.ridersRoutes.tags.${tag}`)}
                </button>
              ))}
            </div>
          </fieldset>
          <p className="text-[11px] text-leaf-muted">
            {t('greenest.ridersRoutes.upload.publicNote')}
          </p>
          <button
            className="flex items-center justify-center gap-2 rounded-full bg-leaf-forest px-4 py-2.5 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss disabled:cursor-not-allowed disabled:bg-leaf-sand disabled:text-leaf-muted"
            disabled={publishing || name.trim().length < 3}
            onClick={publish}
            type="button"
          >
            {t(
              publishing
                ? 'greenest.ridersRoutes.upload.publishing'
                : 'greenest.ridersRoutes.upload.publish',
            )}
          </button>
        </>
      )}
      {error && (
        <p className="text-xs text-red-700" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
