/**
 * Single place for calls to the GreenestBikeRoute FastAPI backend
 * (`uvicorn backend.app:app` in the repository root).
 *
 * Components should import from here instead of calling fetch directly, so
 * the backend URL and response shapes only need to change in one file.
 */
import type { FeatureCollection, LineString } from 'geojson'
import type { RouteCollection, RouteRequest } from '@/types/greenest'

export const GREENEST_API_URL =
  process.env.NEXT_PUBLIC_GREENEST_API_URL ?? 'http://127.0.0.1:8000'

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
export function fetchRoute(
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
}

/** GET /roughness: measured street roughness (0-100) for a map overlay. */
export function fetchRoughness(
  signal?: AbortSignal,
): Promise<FeatureCollection<LineString, { roughness: number | null }>> {
  return getJson('/roughness', signal)
}
