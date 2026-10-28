/**
 * Single place for calls to the GreenestBikeRoute FastAPI backend
 * (`uvicorn backend.app:app` in the repository root).
 *
 * Components should import from here instead of calling fetch directly, so
 * the backend URL and response shapes only need to change in one file.
 */
import type { FeatureCollection, LineString } from 'geojson'
import type {
  GradeCollection,
  OverlayName,
  RouteComparison,
  RouteOptions,
  RouteRequest,
} from '@/types/greenest'

export const GREENEST_API_URL =
  process.env.NEXT_PUBLIC_GREENEST_API_URL ?? 'http://127.0.0.1:8001'

/** The backend's own defaults (routing/costs.py), used when the page opens. */
export const DEFAULT_ROUTE_OPTIONS: RouteOptions = {
  bump: 10,
  danger: 25,
  pm: 0.5,
  stop: 0.5,
  bikeFriendly: 0,
  preferTime: false,
  departTime: '',
  shade: 0.5,
  dark: 1,
}

export class GreenestApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'GreenestApiError'
    this.status = status
  }
}

/** Turns FastAPI's `detail` into one readable line. */
function errorMessage(detail: unknown, status: number): string {
  // 400 from routing: a plain sentence, e.g. "start point is 900 m from the nearest Heilbronn street".
  if (typeof detail === 'string') {
    return detail
  }
  // 422 from validation: a list of { msg, ... } objects.
  if (Array.isArray(detail)) {
    return detail.map(d => d?.msg ?? String(d)).join(' ')
  }
  return `Request failed with status ${status}`
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${GREENEST_API_URL}${path}`, { signal })
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      throw error
    }
    throw new GreenestApiError(
      `The routing service at ${GREENEST_API_URL} is not reachable.`,
    )
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new GreenestApiError(
      errorMessage(body?.detail, response.status),
      response.status,
    )
  }
  return response.json() as Promise<T>
}

/** The query string shared by /route, /route/compare and /route/grade. */
function routeParams({ from, to, options }: RouteRequest): URLSearchParams {
  const params = new URLSearchParams({
    from_lat: String(from[1]),
    from_lon: String(from[0]),
    to_lat: String(to[1]),
    to_lon: String(to[0]),
    bump_penalty: String(options.bump),
    danger_penalty: String(options.danger),
    pm_penalty: String(options.pm),
    stop_penalty: String(options.stop),
    prefer_bike_friendly: String(options.bikeFriendly),
    prefer_time: String(options.preferTime),
    shade_penalty: String(options.shade),
    dark_penalty: String(options.dark),
  })
  // Without a departure time the backend ignores shade and lighting, so leave it out.
  if (options.departTime) {
    params.set('depart_time', options.departTime)
  }
  return params
}

/** GET /route/compare: the route for the given options next to the shortest route. */
export function fetchRouteComparison(
  request: RouteRequest,
  signal?: AbortSignal,
): Promise<RouteComparison> {
  return getJson<RouteComparison>(
    `/route/compare?${routeParams(request)}`,
    signal,
  )
}

/**
 * GET /route/grade: the route for the same request, cut into pieces coloured by steepness.
 * Display only: it doesn't change which route is picked. 503 if the server has no elevation data.
 */
export function fetchRouteGrade(
  request: RouteRequest,
  signal?: AbortSignal,
): Promise<GradeCollection> {
  return getJson<GradeCollection>(
    `/route/grade?${routeParams(request)}`,
    signal,
  )
}

/**
 * GET /<name>: a static map overlay as GeoJSON (see the backend's /docs for each one's values).
 * `/score` uses the backend's default settings here, i.e. an overall score for the city.
 */
export function fetchOverlay(
  name: OverlayName,
  signal?: AbortSignal,
): Promise<FeatureCollection> {
  return getJson<FeatureCollection>(`/${name}`, signal)
}

/** GET /roughness: measured street roughness (0-100) for a map overlay. */
export function fetchRoughness(
  signal?: AbortSignal,
): Promise<FeatureCollection<LineString, { roughness: number | null }>> {
  return getJson('/roughness', signal)
}

/* export class GreenestApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'GreenestApiError'
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${GREENEST_API_URL}${path}`, { signal })
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      throw error
    }
    throw new GreenestApiError(
      `The routing service at ${GREENEST_API_URL} is not reachable.`,
    )
  }

  if (!response.ok) {
    // FastAPI puts the reason in `detail`, e.g. "start point is 900 m from the nearest Heilbronn street".
    const body = await response.json().catch(() => null)
    throw new GreenestApiError(
      body?.detail ?? `Request failed with status ${response.status}`,
      response.status,
    )
  }
  return response.json() as Promise<T>
}

/** GET /route: bike route from A to B as a GeoJSON FeatureCollection with one LineString. */
/* export function fetchRoute(
  { from, to, penalty }: RouteRequest,
  signal?: AbortSignal,
): Promise<RouteCollection> {
  const params = new URLSearchParams({
    from_lat: String(from[1]),
    from_lon: String(from[0]),
    to_lat: String(to[1]),
    to_lon: String(to[0]),
  })
  if (penalty !== undefined) {
    params.set('penalty', String(penalty))
  }
  return getJson<RouteCollection>(`/route?${params}`, signal)
} */

/**
export function fetchRoughness(
  signal?: AbortSignal,
): Promise<FeatureCollection<LineString, { roughness: number | null }>> {
  return getJson('/roughness', signal)
}

function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => d.msg).join(' ')
  return `Request failed with status ${status}`
}

// In getJson, replace the message line with:
//   errorMessage(body?.detail, response.status), response.status

function routeParams({ from, to, penalties }: RouteRequest): URLSearchParams {
  return new URLSearchParams({
    from_lat: String(from[1]),
    from_lon: String(from[0]),
    to_lat: String(to[1]),
    to_lon: String(to[0]),
    bump_penalty: String(penalties?.bump ?? 10),
    danger_penalty: String(penalties?.danger ?? 25),
    pm_penalty: String(penalties?.pm ?? 0.5),
  })
}

export function fetchRouteComparison(
  request: RouteRequest,
  signal?: AbortSignal,
): Promise<RouteComparison> {
  return getJson<RouteComparison>(`/route/compare?${routeParams(request)}`, signal)
} */
