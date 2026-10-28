import type { Feature, FeatureCollection, LineString } from 'geojson'

/** [longitude, latitude], the order GeoJSON and MapLibre use. */
export type LngLat = [number, number]

export type EnvironmentLayerId =
  | 'environmental-score'
  | 'air-quality'
  | 'cycling-infrastructure'
  | 'bike-friendly'
  | 'overtaking'
  | 'stop-and-go'
  | 'speed'
  | 'shade'
  | 'lighting'
  | 'noise'
  | 'green-spaces'

/** Map overlays served by the backend, by their endpoint name (GET /<name>). */
export type OverlayName =
  | 'score'
  | 'bike-friendly-streets'
  | 'danger'
  | 'flow'
  | 'speed'
  | 'shade'
  | 'lighting'

/** Where the values shown for a layer come from. */
export type DataAvailability =
  | 'measured' // real measurements from a named source
  | 'estimated' // derived or modelled, must be labelled as such
  | 'demo' // sample data for the UI only, never shown as a measurement
  | 'unavailable' // not connected yet

export type EnvironmentLayer = {
  id: EnvironmentLayerId
  unit?: string
  /** Planned or connected data source, shown next to the values. */
  source?: string
  availability: DataAvailability
  /** Backend endpoint the layer is loaded from (when first switched on); static layers have none. */
  overlay?: OverlayName
  /** Legend entries from best to worst environmental condition. */
  legend: Array<{ color: string; label: string }>
}

/** One ~500 m grid cell of public/map-data/areas.geojson (see scripts/build-map-data.mjs). */
export type AreaProperties = {
  cell: string
  /** Mean traffic + fine-dust risk index (0..1); null with too few measurement points. */
  pm_risk: number | null
  pm_points: number
  /** Mean overtaking risk index (0..1); null with too few measured manoeuvres. */
  overtaking_risk: number | null
  overtaking_points: number
  /** Length-weighted mean surface roughness (0..100); null if no street was measured. */
  roughness: number | null
  roughness_measured_m: number
}

/** Properties of each route feature returned by `/route` and `/route/compare` (see backend/schemas.py). */
export type RouteProperties = {
  // The settings the route was planned with (all 0 / false for the shortest route).
  bump_penalty: number
  danger_penalty: number
  pm_penalty: number
  stop_penalty: number
  prefer_time: boolean
  shade_penalty: number
  dark_penalty: number
  prefer_bike_friendly: number
  /** The requested departure time (Heilbronn local time, ISO 8601), or null. */
  depart_time: string | null
  /** True if the sun is up at depart_time (shade counted), false after dark (lighting counted), null without depart_time. */
  daylight: boolean | null

  // What the route is like.
  length_m: number
  /** Expected riding time in seconds, from measured cyclist speeds. */
  duration_s: number
  /** Roughness 0–100 over the measured part; null if nothing was measured. */
  mean_roughness: number | null
  measured_share: number
  danger_points: number
  danger_risk: number
  /** Air rank 0–1 (0.5 = typical); null if nothing was measured. */
  mean_pm_risk: number | null
  pm_measured_share: number
  /** Stop-and-go 0–1 (higher = more stopping); null if nothing was measured. */
  mean_stop_go: number | null
  stop_measured_share: number
  /** Share in shade 0–1, only by day with depart_time. */
  mean_shade: number | null
  /** Chance the streets are lit 0–1. */
  mean_lit: number | null
  lifts: number
}

export type RouteFeature = Feature<LineString, RouteProperties>
export type RouteCollection = FeatureCollection<LineString, RouteProperties>

export type RouteComparison = {
  route: RouteFeature
  shortest: RouteFeature
  /** How much longer the route is than the shortest one, in %. */
  detour_pct: number
  /** How much more time the route takes than the shortest one, in %; negative if faster. */
  extra_time_pct: number
  same_path: boolean
}

/** Everything the rider can set in the Plan a Trip form. Limits match the backend. */
export type RouteOptions = {
  /** 0–50: avoid bumpy streets. */
  bump: number
  /** 0–100: metres of detour per close-overtaking spot avoided. */
  danger: number
  /** 0–5: avoid bad air. */
  pm: number
  /** 0–5: avoid traffic lights and stop-and-go. */
  stop: number
  /** 0–5: prefer bike paths, bike lanes and bike routes. */
  bikeFriendly: number
  /** Plan by riding time (fastest) instead of length (shortest). */
  preferTime: boolean
  /** Departure as "YYYY-MM-DDTHH:mm" in Heilbronn time, or "" for none. */
  departTime: string
  /** 0–5, by day (needs departTime): prefer shaded streets. */
  shade: number
  /** 0–5, after dark (needs departTime): prefer lit streets. */
  dark: number
}

export type RouteRequest = {
  from: LngLat
  to: LngLat
  options: RouteOptions
}

export type RouteKind = 'shortest' | 'greenest'

export type HighlightPlace = {
  id: string
  name: string
  description: string
  category: 'park' | 'riverside' | 'green-space' | 'destination'
  imageUrl?: string
  /** Approximate point; omitted until verified. */
  location?: LngLat
  /** True while the card text is placeholder content. */
  demo: boolean
}

/** One piece of the route from `/route/grade`, all with the same steepness class. */
export type GradeProperties = {
  /** Rise / length in %, positive uphill in the travel direction. */
  grade_pct: number
  severity: 'flat' | 'gentle' | 'noticeable' | 'steep' | 'very_steep'
  /** Suggested line colour for the severity (#rrggbb). */
  color: string
  length_m: number
  rise_m: number
  start_m: number
}

export type GradeSummary = {
  length_m: number
  climb_m: number
  descent_m: number
  start_elevation_m: number
  end_elevation_m: number
  max_grade_pct: number
  max_descent_grade_pct: number
}

/** `/route/grade`: the same path as `/route`, cut into pieces by steepness, plus totals. */
export type GradeCollection = FeatureCollection<LineString, GradeProperties> & {
  summary: GradeSummary
}