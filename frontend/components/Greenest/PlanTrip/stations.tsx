import { TrainFront } from 'lucide-react'
import type {
  LngLat,
  PlaceProperties,
  TransitStopFeature,
} from '@/types/greenest'
import { SBAHN_COLOR, stationKind, TRAIN_COLOR } from './transitLayers'

/** For name search: case, accents and umlauts don't matter (Sülmertor = sulmertor). */
export function folded(text: string) {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/**
 * Stations whose name (or the name of a stop merged into it: "Willy-Brandt" finds the
 * Hauptbahnhof) contains `query`; a word starting with it first, then by name.
 */
export function matchStations(
  stations: TransitStopFeature[],
  query: string,
  max: number,
): TransitStopFeature[] {
  const q = folded(query.trim())
  if (!q) {
    return []
  }
  const starts = (name: string) =>
    name.split(/[\s,/(-]+/).some(word => word.startsWith(q))
  return stations
    .map(s => {
      const names = [s.properties.name, ...(s.properties.also ?? [])].map(
        folded,
      )
      // Its own name if that matches, else the stop's that does.
      return { s, name: names.find(n => n.includes(q)) }
    })
    .filter((m): m is { s: TransitStopFeature; name: string } =>
      Boolean(m.name),
    )
    .sort(
      (a, b) =>
        Number(starts(b.name)) - Number(starts(a.name)) ||
        a.s.properties.name.localeCompare(b.s.properties.name),
    )
    .slice(0, max)
    .map(({ s }) => s)
}

/** Metres between two points; good enough within a city. */
export function metresBetween([lng1, lat1]: LngLat, [lng2, lat2]: LngLat) {
  const y = (lat2 - lat1) * 111_320
  const x = (lng2 - lng1) * 111_320 * Math.cos((lat1 * Math.PI) / 180)
  return Math.hypot(x, y)
}

/**
 * A place of the search this close to a stop of a station is that station: OpenStreetMap puts
 * its own point on each platform, a little away from the timetable's.
 */
const STATION_PLACE_M = 150

/** OSM categories of stops and stations: such a place next to a station is the station itself. */
function isStop({ category, type }: PlaceProperties) {
  return (
    category === 'railway' ||
    category === 'public_transport' ||
    (category === 'building' && type === 'train_station')
  )
}

/**
 * The station a place of the search stands for, or null: a railway place (a station, a
 * platform, a tram stop) within STATION_PLACE_M of one of its stops. So "Harmonie" found by the place
 * search and Harmonie from the timetable are not listed twice, and either one is a station
 * for the mode "Bike + train".
 */
export function stationOfPlace(
  stations: TransitStopFeature[],
  place: PlaceProperties,
  at: LngLat,
): TransitStopFeature | null {
  if (!isStop(place)) {
    return null
  }
  let best: TransitStopFeature | null = null
  let bestM = STATION_PLACE_M
  for (const s of stations) {
    const [lng, lat] = s.geometry.coordinates
    const stops: LngLat[] = s.properties.stops?.length
      ? s.properties.stops.map(p => [p.lon, p.lat])
      : [[lng, lat]]
    const m = Math.min(...stops.map(p => metresBetween(at, p)))
    if (m <= bestM) {
      best = s
      bestM = m
    }
  }
  return best
}

/** The white S on a green disc, or the white train on a blue one, as on the map. */
export function StationBadge({ lines }: { lines: string[] }) {
  const sbahn = stationKind(lines) === 'sbahn'
  return (
    <span
      aria-hidden
      className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[12px] font-bold leading-none text-white"
      style={{ backgroundColor: sbahn ? SBAHN_COLOR : TRAIN_COLOR }}
    >
      {sbahn ? 'S' : <TrainFront className="h-3 w-3" strokeWidth={2.5} />}
    </span>
  )
}
