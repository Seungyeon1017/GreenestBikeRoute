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
