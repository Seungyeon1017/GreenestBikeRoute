import type {
  Feature,
  FeatureCollection,
  LineString,
  MultiPolygon,
  Point,
  Polygon,
} from 'geojson'

/** [longitude, latitude], the order GeoJSON and MapLibre use. */
export type LngLat = [number, number]

export type EnvironmentLayerId =
  | 'environmental-score'
  | 'air-quality'
  | 'surface-roughness'
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
  | 'mapped' // tagged in OpenStreetMap, not measured
  | 'no-data' // dataset connected, but no measurement at this place
  | 'unavailable' // not connected yet

export type EnvironmentLayer = {
  id: EnvironmentLayerId
  unit?: string
  /** Planned or connected data source, shown next to the values. */
  source?: string
  availability: DataAvailability
  /** Backend endpoint the layer is loaded from (when first switched on); static layers have none. */
  overlay?: OverlayName
  /**
   * Colours the streets themselves. Only one such layer is shown at a time,
   * since two would paint over each other on the same streets.
   */
  colorsStreets?: boolean
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
  /** The shade time slot used by day (ISO 8601, e.g. "2026-07-21T12:00+02:00"), null otherwise. */
  shade_slot: string | null

  // What the route is like.
  length_m: number
  /** Expected riding time in seconds, from measured cyclist speeds. */
  duration_s: number
  /** Height gained in metres; null without elevation data (kcal then leaves climbs out). */
  climb_m: number | null
  /** Roughness 0–100 over the measured part; null if nothing was measured. */
  mean_roughness: number | null
  measured_share: number
  /** Share whose roughness is estimated from nearby measured streets. */
  estimated_share: number
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
  /** Streets riders reported closed (status reported or unconfirmed) that the route still rides: worth a warning. */
  reported_closures: number
  /** Rough energy use for riding the route; an estimate, show it rounded. */
  kcal: number

  // Metres on the bad streets of each factor ("Why this route?"); null when the factor doesn't apply.
  bumpy_m: number
  bad_air_m: number
  stop_go_m: number
  /** Only by day with depart_time. */
  sunny_m: number | null
  /** Only after dark with depart_time. */
  unlit_m: number | null
  /** More is better here. */
  bike_friendly_m: number

  /** The route as stretches with what is measured on them, in riding order. */
  segments: RouteSegment[]
}

/** The "Why this route?" factors, named after their totals in RouteProperties. */
export type RouteFlag =
  | 'bumpy_m'
  | 'danger_points'
  | 'bad_air_m'
  | 'stop_go_m'
  | 'sunny_m'
  | 'unlit_m'
  | 'bike_friendly_m'

/** The kinds of way a stretch can be on (see backend/schemas.py). */
export type WayKind =
  | 'crossing'
  | 'sidewalk'
  | 'cycleway'
  | 'footway'
  | 'path'
  | 'track'
  | 'service'
  | 'pedestrian'

/** A stretch of a route: consecutive streets with the same name and flags (see backend/schemas.py). */
export type RouteSegment = {
  /** First and last index (inclusive) in the route's coordinates. */
  from_index: number
  to_index: number
  start_m: number
  length_m: number
  /** OSM street name, or for a way without one the road it runs beside (`along`); null if none. */
  name: string | null
  /** Kind of way from OSM; null for an ordinary road (or road and sidewalk together). */
  way: WayKind | null
  along: boolean
  /** The factors this stretch counts towards, by the backend's thresholds. */
  flags: RouteFlag[]
  roughness: number | null
  danger_points: number
  pm_risk: number | null
  stop_go: number | null
  speed_kmh: number | null
  /** Share in shade, only by day with depart_time. */
  shade: number | null
  lit: number | null
  bike_friendly: boolean
  pushed: boolean
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

/** /route/compare for every departure in [from, to), "HH:MM" Heilbronn time. */
export type DayPeriod = RouteComparison & { from: string; to: string }

/** GET /route/day: the periods of one day with the same sky (one shade slot by day, or dark), in order. */
export type DayRoutes = {
  /** "YYYY-MM-DD" */
  date: string
  periods: DayPeriod[]
}

/** Everything the rider can set in the Plan a Trip form. Limits match the backend. */
export type RouteOptions = {
  /** 0–10 points: avoid bumpy streets (each point: +25 % on the bumpiest streets). */
  bump: number
  /** 0–100: metres of detour per close-overtaking spot avoided. */
  danger: number
  /** 0–10 points: avoid bad air. */
  pm: number
  /** 0–10 points: avoid traffic lights and stop-and-go. */
  stop: number
  /** 0–10 points: prefer bike paths, bike lanes and bike routes. */
  bikeFriendly: number
  /** Plan by riding time (fastest) instead of length (shortest). */
  preferTime: boolean
  /** Departure as "YYYY-MM-DDTHH:mm" in Heilbronn time, or "" for none. */
  departTime: string
  /** 0–10 points, by day (needs departTime): prefer shaded streets. */
  shade: number
  /** 0–10 points, after dark (needs departTime): prefer lit streets. */
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
  /** Photo credit, shown on the photo; required for CC licenses. */
  imageCredit?: {
    author: string
    /** Short license name, e.g. "CC BY-SA 4.0" or "Public domain". */
    license: string
    /** Commons page of the file. */
    sourceUrl: string
  }
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

/** A place from `/geocode`: one "did you mean" candidate. */
export type PlaceProperties = {
  /** Full name with street and district. */
  label: string
  /** Short name, e.g. "Rathaus Heilbronn"; null for a plain address. */
  name: string | null
  category: string | null
  type: string | null
}

export type PlaceCollection = FeatureCollection<Point, PlaceProperties> & {
  attribution: string
}

export type SharingVehicleKind = 'bike' | 'scooter'
/** Which shared vehicles to show or rent: e-bikes, e-scooters or both. */
export type SharingVehicleChoice = 'all' | SharingVehicleKind

/** A shared vehicle free to rent now, from `/sharing`. */
export type VehicleProperties = {
  provider: string
  vehicle: SharingVehicleKind
  vehicle_id: string
  electric: boolean
  battery_pct: number | null
  range_m: number | null
  /** As the provider publishes it, e.g. "€1.00 to unlock + €0.44/min". */
  price: string | null
  rent_url: string | null
  last_reported: string | null
  /** Metres from the start, when near_lat/near_lon was sent. */
  distance_m?: number | null
}

export type VehicleFeature = Feature<Point, VehicleProperties>

export type VehicleCollection = FeatureCollection<Point, VehicleProperties> & {
  /** When the feed was read (ISO 8601, UTC). */
  updated: string
  attribution: string
}

/** A parking zone from `/sharing/zones` with live counts. */
export type ZoneProperties = {
  provider: string
  name: string
  bikes_available: number
  scooters_available: number
  bike_capacity: number | null
  scooter_capacity: number | null
  distance_m?: number | null
}

export type ZoneCollection = FeatureCollection<Point, ZoneProperties> & {
  updated: string
  attribution: string
}

/** Where a ride may end in a geofencing zone: anywhere, only at a parking zone, or not at all. */
export type EndRule = 'anywhere' | 'parking_zone' | 'no'

/** `/sharing/geofencing`: the provider's zones (Polygon or MultiPolygon), per vehicle kind. */
export type GeofencingCollection = FeatureCollection<
  Polygon | MultiPolygon,
  {
    provider: string
    name: string | null
    order: number
    bike?: EndRule | null
    scooter?: EndRule | null
  }
> & { updated: string; attribution: string }

export type WalkLeg = Feature<
  LineString,
  { mode: 'walk'; length_m: number; duration_s: number; kcal: number }
>

export type RideLeg = Feature<
  LineString,
  RouteProperties & {
    mode: SharingVehicleKind
    kcal: number
    /** Metres an e-scooter is pushed where it may not ride; 0 for bikes. */
    pushed_m: number
  }
>

/** `/route/sharing`: walk to a shared vehicle, ride it, walk to the end. */
export type SharingTrip = {
  vehicle: VehicleFeature
  /** The parking zone the ride ends at, or null when it ends elsewhere. */
  zone: Feature<Point, ZoneProperties> | null
  return_point: Feature<
    Point,
    {
      rule: 'anywhere' | 'parking_zone'
      at_destination: boolean
      name: string | null
    }
  >
  /** Walk, ride, walk. */
  legs: [WalkLeg, RideLeg, WalkLeg]
  duration_s: number
  walk_m: number
  ride_m: number
  /** Riding time in seconds, what the per-minute price applies to. */
  ride_s: number
  kcal: number
  updated: string
  attribution: string
}

/**
 * closed: 3+ independent live reports, routes don't use it. reported: fewer, routes avoid it where they can.
 * unconfirmed: the reports lapsed less than 3 days ago; routes still avoid it, riders nearby get asked.
 * open: only in the answer to a report or `/confirm`, when riders' answers just lifted it.
 */
export type ClosureStatus = 'closed' | 'reported' | 'unconfirmed' | 'open'

/** A street segment riders reported closed, from `/reports/closures`. */
export type ClosureProperties = {
  /** "u-v", the OSM node ids at its two junctions; the id for `/confirm`. */
  segment: string
  osm_way_ids: number[]
  status: ClosureStatus
  /** Live independent reports; "still closed" answers count as reports. */
  reports: number
  /** Riders who said it is open again since the last report; 2 lift it. */
  open_reports: number
  note: string | null
  /** ISO 8601, UTC. */
  last_report: string
  /** When the last report lapses (ISO 8601, UTC). */
  expires: string
}

export type ClosureFeature = Feature<LineString, ClosureProperties>
export type ClosureCollection = FeatureCollection<LineString, ClosureProperties>

/** rideable: a footway bikes may and do ride on that routing leaves out; other: any other map mistake. */
export type MappingKind = 'rideable' | 'other'

/** A rider's mapping report, from `/reports/mapping` (pending until a maintainer checks it). */
export type MappingProperties = {
  id: number
  kind: MappingKind
  osm_way_id: number | null
  note: string | null
  status: 'pending' | 'approved' | 'rejected'
  created: string
  resolved: string | null
}

export type MappingFeature = Feature<Point, MappingProperties>
export type MappingCollection = FeatureCollection<Point, MappingProperties>

/** What "Report a problem" reports at the next map click: a closed street, or a mapping mistake. */
export type ReportKind = 'closure' | MappingKind
