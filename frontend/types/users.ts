/**
 * Shapes of the users endpoints (backend/users/schemas.py). Kept apart from
 * types/greenest.ts, which belongs to the routing API.
 */

/** GET /users/me, POST /users. */
export type User = {
  id: number
  email: string
  display_name: string | null
  /** ISO 8601. */
  created_at: string
}

/** Route options as the backend stores them: the query parameter names of /route/compare. */
export type SavedRouteOptions = {
  bump_penalty: number
  danger_penalty: number
  pm_penalty: number
  stop_penalty: number
  prefer_bike_friendly: number
  prefer_time: boolean
  shade_penalty: number
  dark_penalty: number
  depart_time: string | null
}

/** Body of POST /users/me/routes. */
export type SavedRouteInput = {
  start_lon: number
  start_lat: number
  start_label: string | null
  end_lon: number
  end_lat: number
  end_label: string | null
  options: SavedRouteOptions
  length_m: number | null
  duration_s: number | null
}

/** GET /users/me/routes: one saved route. */
export type SavedRoute = SavedRouteInput & {
  id: number
  /** ISO 8601. */
  created_at: string
}

/** The tags a rider can give a leisure route (backend/users/schemas.py RouteTag). */
export const ROUTE_TAGS = [
  'family',
  'view',
  'quiet',
  'river',
  'nature',
  'gravel',
] as const
export type RouteTag = (typeof ROUTE_TAGS)[number]

/** POST /community-routes/preview: a GPX ride as it would be published. */
export type TrackPreview = {
  /** [lon, lat], without the first and last 200 m of the ride. */
  coordinates: [number, number][]
  length_m: number
  /** How long the ride took while moving. */
  moving_s: number
  /** "YYYY-MM-DD" */
  recorded_on: string
  /** The app that wrote the file, e.g. "StravaGPX". */
  creator: string | null
  is_loop: boolean
}

/** A riders' leisure route in a list: everything but the whole line. */
export type CommunityRouteSummary = Omit<TrackPreview, 'coordinates'> & {
  id: number
  name: string
  description: string
  tags: RouteTag[]
  /** The author's display name, or null. */
  author: string | null
  /** [lon, lat] where the line starts. */
  start: [number, number]
  /** At most 40 [lon, lat] points, to draw the route's shape small. */
  preview: [number, number][]
  hearts: number
  hearted: boolean
  saved: boolean
  mine: boolean
  /** Only the author sees routes that aren't published. */
  status: 'published' | 'hidden' | 'removed'
  /** ISO 8601. */
  created_at: string
}

/** GET /community-routes/{id}. */
export type CommunityRoute = CommunityRouteSummary & {
  coordinates: [number, number][]
}

/** GET /community-routes. */
export type CommunityRouteList = {
  routes: CommunityRouteSummary[]
  total: number
}

export type CommunityRouteSort = 'hearts' | 'newest'

/** Body of POST /community-routes, besides the file. */
export type CommunityRouteInput = {
  name: string
  description: string
  tags: RouteTag[]
}
