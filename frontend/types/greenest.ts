import type { Feature, FeatureCollection, LineString } from 'geojson'

/** [longitude, latitude], the order GeoJSON and MapLibre use. */
export type LngLat = [number, number]

export type EnvironmentLayerId =
  | 'air-quality'
  | 'noise'
  | 'green-spaces'
  | 'cycling-infrastructure'
  | 'environmental-score'

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

/** Properties of the route feature returned by the FastAPI `/route` endpoint. */
export type RouteProperties = {
  bump_penalty: number
  danger_penalty: number
  pm_penalty: number
  stop_penalty: number

  /** Length-weighted over the measured part of the route; null if nothing was measured. */
  length_m: number
  mean_roughness: number | null
  measured_share: number
  danger_points: number
  danger_risk: number
  mean_pm_risk: number | null
  /** Share of the route length with a roughness measurement, 0..1. */
  pm_measured_share: number
  mean_stop_go: number | null
  stop_measured_share: number
  
}

export type RouteFeature = Feature<LineString, RouteProperties>
export type RouteCollection = FeatureCollection<LineString, RouteProperties>

export type RouteComparison = {
  route: RouteFeature
  shortest: RouteFeature
  detour_pct: number
  same_path: boolean
}

/** The three sliders. Values match the backend limits: 0–50, 0–100, 0–5. */
export type Penalties = { bump: number; danger: number; pm: number }

export type RouteRequest = {
  from: LngLat
  to: LngLat
  penalties?: Partial<Penalties>
}

export type RoutePreferences = {
  preferGreener: boolean
  preferQuieter: boolean
  preferCycleLanes: boolean
  /** Extra minutes the user accepts compared with the fastest route. */
  maxExtraMinutes: number
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
