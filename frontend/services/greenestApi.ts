/**
 * Single place for calls to the GreenestBikeRoute FastAPI backend
 * (`uvicorn backend.app:app` in the repository root).
 *
 * Components should import from here instead of calling fetch directly, so
 * the backend URL and response shapes only need to change in one file.
 */
import type { FeatureCollection, LineString } from 'geojson'
import type {
  ClosureCollection,
  ClosureFeature,
  DayRoutes,
  FootwayFeature,
  GeofencingCollection,
  GradeCollection,
  GreenStreetCollection,
  LngLat,
  MappingCollection,
  MappingFeature,
  MappingKind,
  OverlayName,
  PlaceCollection,
  RouteComparison,
  RouteOptions,
  RouteRequest,
  SharingTrip,
  SharingVehicleChoice,
  StreetSegmentFeature,
  VehicleCollection,
  ZoneCollection,
} from '@/types/greenest'

export const GREENEST_API_URL =
  process.env.NEXT_PUBLIC_GREENEST_API_URL ?? 'http://127.0.0.1:8001'

/** The backend's own defaults (routing/costs.py, DEFAULT_*_PENALTY), used when the page opens. */
export const DEFAULT_ROUTE_OPTIONS: RouteOptions = {
  bump: 2,
  danger: 10,
  pm: 1,
  stop: 1,
  bikeFriendly: 0,
  preferTime: false,
  departTime: '',
  shade: 2,
  dark: 4,
}

export class GreenestApiError extends Error {
  status?: number
  /** Why, when the backend says so in `detail.code` (e.g. "no_times" for a GPX upload). */
  code?: string

  constructor(message: string, status?: number, code?: string) {
    super(message)
    this.name = 'GreenestApiError'
    this.status = status
    this.code = code
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

async function getJson<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${GREENEST_API_URL}${path}`, { ...init, signal })
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

function postJson<T>(path: string, body: unknown): Promise<T> {
  return getJson<T>(path, undefined, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
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
 * GET /route/day: /route/compare for every departure of the day of options.departTime (today without one),
 * in periods with the same shade slot, or dark.
 */
export function fetchRouteDay(
  request: RouteRequest,
  signal?: AbortSignal,
): Promise<DayRoutes> {
  return getJson<DayRoutes>(`/route/day?${routeParams(request)}`, signal)
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

/** GET /highlights/greenest-streets: the greenest streets bikes have ridden, greenest first. */
export function fetchGreenestStreets(
  limit: number,
  signal?: AbortSignal,
): Promise<GreenStreetCollection> {
  return getJson(`/highlights/greenest-streets?limit=${limit}`, signal)
}

/**
 * GET /geocode: places in Heilbronn matching what the rider typed, best first.
 * Needs at least 3 characters (422 otherwise); 503 if the place search is down.
 */
export function fetchPlaces(
  query: string,
  signal?: AbortSignal,
  limit = 5,
): Promise<PlaceCollection> {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return getJson<PlaceCollection>(`/geocode?${params}`, signal)
}

/** near_lat / near_lon: the backend then sorts by distance and adds `distance_m`. */
function nearParams(near: LngLat | null, limit?: number): URLSearchParams {
  const params = new URLSearchParams()
  if (near) {
    params.set('near_lat', String(near[1]))
    params.set('near_lon', String(near[0]))
  }
  if (limit) {
    params.set('limit', String(limit))
  }
  return params
}

/** GET /sharing: shared e-bikes and e-scooters free to rent now. 503 if the feed can't be read. */
export function fetchSharedVehicles(
  vehicle: SharingVehicleChoice,
  near: LngLat | null,
  signal?: AbortSignal,
): Promise<VehicleCollection> {
  const params = nearParams(near)
  params.set('vehicle', vehicle)
  return getJson<VehicleCollection>(`/sharing?${params}`, signal)
}

/** GET /sharing/zones: parking zones with how many vehicles stand there now. */
export function fetchSharingZones(
  near: LngLat | null,
  signal?: AbortSignal,
): Promise<ZoneCollection> {
  return getJson<ZoneCollection>(`/sharing/zones?${nearParams(near)}`, signal)
}

/** GET /sharing/geofencing: where shared vehicles may (not) be left. Changes rarely. */
export function fetchGeofencing(
  signal?: AbortSignal,
): Promise<GeofencingCollection> {
  return getJson<GeofencingCollection>('/sharing/geofencing', signal)
}

/**
 * GET /route/sharing: walk to a free shared vehicle, ride it with the same options as /route, walk to the end.
 * 400 when no vehicle is within reach, 503 when the sharing feed can't be read.
 */
export function fetchSharingTrip(
  request: RouteRequest,
  vehicle: SharingVehicleChoice,
  signal?: AbortSignal,
): Promise<SharingTrip> {
  const params = routeParams(request)
  params.set('vehicle', vehicle)
  return getJson<SharingTrip>(`/route/sharing?${params}`, signal)
}

/** GET /reports/closures: streets riders reported closed (closed, reported or unconfirmed). */
export function fetchClosures(
  signal?: AbortSignal,
): Promise<ClosureCollection> {
  return getJson<ClosureCollection>('/reports/closures', signal)
}

/** GET /reports/mapping: riders' mapping reports still waiting for a maintainer. */
export function fetchMappingReports(
  signal?: AbortSignal,
): Promise<MappingCollection> {
  return getJson<MappingCollection>('/reports/mapping', signal)
}

/**
 * POST /reports/closures: street segment `segment` ("u-v") is closed. `until` (YYYY-MM-DD) is the last closed day,
 * if known; without it the report counts for 24 h. 400 when the graph has no such segment or the date is past.
 */
export function reportClosure(
  segment: string,
  reporterId: string | undefined,
  note: string | undefined,
  until: string | undefined,
): Promise<ClosureFeature> {
  return postJson<ClosureFeature>('/reports/closures', {
    segment,
    reporter_id: reporterId,
    note,
    until,
  })
}

function pointParams(at: LngLat): URLSearchParams {
  return new URLSearchParams({ lat: String(at[1]), lon: String(at[0]) })
}

/** GET /reports/segment: the street segment a click at `at` would report closed. 400 if no street is within 50 m. */
export function fetchReportSegment(
  at: LngLat,
  signal?: AbortSignal,
): Promise<StreetSegmentFeature> {
  return getJson<StreetSegmentFeature>(
    `/reports/segment?${pointParams(at)}`,
    signal,
  )
}

/** GET /reports/footway: the footway routing leaves out nearest to `at`. 400 if none is within 50 m. */
export function fetchReportFootway(
  at: LngLat,
  signal?: AbortSignal,
): Promise<FootwayFeature> {
  return getJson<FootwayFeature>(`/reports/footway?${pointParams(at)}`, signal)
}

/** POST /reports/closures/{segment}/confirm: one tap on a known closure, still closed or open again. */
export function confirmClosure(
  segment: string,
  stillClosed: boolean,
  reporterId: string | undefined,
): Promise<ClosureFeature> {
  return postJson<ClosureFeature>(
    `/reports/closures/${encodeURIComponent(segment)}/confirm`,
    { still_closed: stillClosed, reporter_id: reporterId },
  )
}

/** POST /reports/mapping: the map is wrong at `at`, e.g. a footway bikes ride on. Pending until checked. */
export function reportMapping(
  at: LngLat,
  kind: MappingKind,
  reporterId: string | undefined,
  note: string | undefined,
  osmWayId?: number,
): Promise<MappingFeature> {
  return postJson<MappingFeature>('/reports/mapping', {
    lat: at[1],
    lon: at[0],
    kind,
    osm_way_id: osmWayId,
    reporter_id: reporterId,
    note,
  })
}
