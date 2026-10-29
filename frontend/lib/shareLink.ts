/**
 * Links that open Plan trip for someone else: a planned trip (start,
 * destination and the options that differ from the defaults) or a riders'
 * leisure route. Nothing is stored: the link carries it all.
 */
import { DEFAULT_ROUTE_OPTIONS } from '@/services/greenestApi'
import { fromSavedOptions, toSavedOptions } from '@/services/usersApi'
import type { LngLat, RouteOptions } from '@/types/greenest'
import type { SavedRouteOptions } from '@/types/users'

export type SharedTrip = {
  start: LngLat | null
  end: LngLat | null
  startLabel: string
  endLabel: string
  options: RouteOptions
}

const point = ([lng, lat]: LngLat) => `${lng.toFixed(5)},${lat.toFixed(5)}`

function readPoint(value: string | null): LngLat | null {
  const [lng, lat] = (value ?? '').split(',').map(Number)
  return value && Number.isFinite(lng) && Number.isFinite(lat)
    ? [lng, lat]
    : null
}

/**
 * /plan-trip?from=lng,lat&fromName=…&to=lng,lat&name=…, plus each option that
 * differs from the default, under its /route/compare name (bump_penalty=6).
 * `to` and `name` are what Highlights' "Auf Karte zeigen" already sends.
 */
export function tripLink(
  start: LngLat,
  end: LngLat,
  startLabel: string,
  endLabel: string,
  options: RouteOptions,
): string {
  const query = new URLSearchParams({ from: point(start) })
  if (startLabel) {
    query.set('fromName', startLabel)
  }
  query.set('to', point(end))
  if (endLabel) {
    query.set('name', endLabel)
  }
  const chosen = toSavedOptions(options)
  const defaults = toSavedOptions(DEFAULT_ROUTE_OPTIONS)
  for (const key of Object.keys(chosen) as (keyof SavedRouteOptions)[]) {
    if (chosen[key] !== defaults[key] && chosen[key] !== null) {
      query.set(key, String(chosen[key]))
    }
  }
  return `${window.location.origin}/plan-trip?${query}`
}

/** The trip in a link from tripLink, or null if the page has no `to` and no `from`. */
export function readTripLink(params: URLSearchParams): SharedTrip | null {
  const start = readPoint(params.get('from'))
  const end = readPoint(params.get('to'))
  if (!start && !end) {
    return null
  }
  const saved = toSavedOptions(DEFAULT_ROUTE_OPTIONS)
  const numbers = saved as unknown as Record<string, number>
  for (const key of Object.keys(saved) as (keyof SavedRouteOptions)[]) {
    const value = params.get(key)
    if (value === null) {
      continue
    }
    if (key === 'prefer_time') {
      saved.prefer_time = value === 'true'
    } else if (key === 'depart_time') {
      saved.depart_time = value
    } else if (Number.isFinite(Number(value))) {
      numbers[key] = Number(value)
    }
  }
  return {
    start,
    end,
    startLabel: params.get('fromName') ?? '',
    endLabel: params.get('name') ?? '',
    options: fromSavedOptions(saved),
  }
}

/** /plan-trip?route=<id>: a riders' leisure route on the map. */
export function communityRouteLink(id: number): string {
  return `${window.location.origin}/plan-trip?route=${id}`
}

export type ShareResult = 'shared' | 'copied' | 'cancelled' | 'manual'

/**
 * The system share sheet where there is one (phones), else the clipboard.
 * 'manual' when neither works (e.g. an insecure page): show the link to copy.
 */
export async function shareLink(
  url: string,
  title: string,
): Promise<ShareResult> {
  if (typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, url })
      return 'shared'
    } catch (err) {
      if ((err as Error).name === 'AbortError') {
        return 'cancelled'
      }
    }
  }
  try {
    await navigator.clipboard.writeText(url)
    return 'copied'
  } catch {
    return 'manual'
  }
}
