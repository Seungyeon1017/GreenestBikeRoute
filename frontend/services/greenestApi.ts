/**
 * Single place for calls to the GreenestBikeRoute FastAPI backend
 * (`uvicorn backend.app:app` in the repository root).
 *
 * Components should import from here instead of calling fetch directly, so
 * the backend URL and response shapes only need to change in one file.
 */
import type { FeatureCollection, LineString } from 'geojson'
import type { RouteRequest, RouteComparison } from '@/types/greenest'

export const GREENEST_API_URL =
  process.env.NEXT_PUBLIC_GREENEST_API_URL ?? 'http://127.0.0.1:8001'

export class GreenestApiError extends Error {
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

/** GET /roughness: measured street roughness (0-100) for a map overlay. */
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
}
