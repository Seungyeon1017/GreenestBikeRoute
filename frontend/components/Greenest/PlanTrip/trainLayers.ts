import type { Feature, FeatureCollection } from 'geojson'
import maplibregl from 'maplibre-gl'
import type { TrainOption, TrainRide, TrainTrip } from '@/types/greenest'
import { ROUTE_COLORS } from './RouteComparison'
import {
  addStationIcons,
  SBAHN_COLOR,
  stationKind,
  TRAIN_COLOR,
} from './transitLayers'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** The bike leg of a bike + train trip: the green of your route. */
export const TRAIN_RIDE_COLOR = ROUTE_COLORS.greenest

/** S-Bahn lines (S4, S41, ...) in the S disc's green, other trains in the train disc's blue. */
export function trainLineColor(line: string) {
  return /^S\d/.test(line) ? SBAHN_COLOR : TRAIN_COLOR
}

/**
 * The bike leg that goes with a train: the ride to (or from) the stop that train uses. A station
 * can have several stops a short walk apart, each with its own ride.
 */
export function rideOf(
  trip: TrainTrip,
  option: TrainOption | null | undefined,
): TrainRide | null {
  const own = trip.rides?.find(r => r.stop_place === option?.stop_place)
  return own?.ride ?? trip.ride
}

/**
 * A trip with a train: the bike leg if there is one (solid green on a white casing), the train
 * as a dashed line along its track (straight between stations whose track the backend doesn't
 * know) with a dot at each stop on the way, and the S or train disc with the name where to get
 * on and off. Pass null to clear it.
 */
export function drawTrainTrip(
  map: maplibregl.Map,
  trip: TrainTrip | null,
  option: TrainOption | null,
) {
  if (!map.getSource('train-trip')) {
    addStationIcons(map)
    map.addSource('train-trip', { type: 'geojson', data: EMPTY })
    map.addSource('train-stops', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'train-trip-casing',
      type: 'line',
      source: 'train-trip',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#ffffff',
        'line-width': ['match', ['get', 'mode'], 'train', 7, 10],
        'line-opacity': 0.9,
      },
    })
    map.addLayer({
      id: 'train-trip-train',
      type: 'line',
      source: 'train-trip',
      filter: ['==', ['get', 'mode'], 'train'],
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': ['get', 'color'],
        'line-width': 4,
        'line-dasharray': [2, 1.5],
      },
    })
    map.addLayer({
      id: 'train-trip-ride',
      type: 'line',
      source: 'train-trip',
      filter: ['==', ['get', 'mode'], 'bike'],
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: { 'line-color': TRAIN_RIDE_COLOR, 'line-width': 6 },
    })
    map.addLayer({
      id: 'train-trip-calls',
      type: 'circle',
      source: 'train-stops',
      filter: ['==', ['get', 'end'], false],
      paint: {
        'circle-radius': 3.5,
        'circle-color': '#ffffff',
        'circle-stroke-color': ['get', 'color'],
        'circle-stroke-width': 2,
      },
    })
    map.addLayer({
      id: 'train-trip-ends',
      type: 'symbol',
      source: 'train-stops',
      filter: ['==', ['get', 'end'], true],
      layout: {
        'icon-image': ['concat', 'station-', ['get', 'kind']],
        'icon-allow-overlap': true,
        'text-field': ['get', 'name'],
        'text-font': [
          'Montserrat SemiBold',
          'Open Sans Bold',
          'Noto Sans Regular',
        ],
        'text-size': 12,
        'text-anchor': 'top',
        'text-offset': [0, 1.1],
        'text-allow-overlap': true,
        'text-max-width': 9,
      },
      paint: {
        'text-color': '#1f3b2c',
        'text-halo-color': '#ffffff',
        'text-halo-width': 2,
      },
    })
  }
  const lines: Feature[] = []
  const stops: Feature[] = []
  if (trip && option) {
    const color = trainLineColor(option.line)
    lines.push({
      type: 'Feature',
      geometry: {
        type: 'LineString',
        // An older backend sends no path: straight from stop to stop.
        coordinates: option.path ?? option.stops.map(s => [s.lon, s.lat]),
      },
      properties: { mode: 'train', color },
    })
    const ride = rideOf(trip, option)
    if (ride) {
      lines.push({ ...ride, properties: { mode: 'bike' } })
    }
    const ends = [trip.board, trip.alight].map(f => f.properties)
    option.stops.forEach((s, i) => {
      const end = i === 0 || i === option.stops.length - 1
      stops.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: {
          end,
          name: s.name,
          color,
          kind: end ? stationKind(ends[i === 0 ? 0 : 1].lines) : null,
        },
      })
    })
  }
  map
    .getSource<maplibregl.GeoJSONSource>('train-trip')
    ?.setData({ type: 'FeatureCollection', features: lines })
  map
    .getSource<maplibregl.GeoJSONSource>('train-stops')
    ?.setData({ type: 'FeatureCollection', features: stops })
}

/**
 * What the map zooms to: the bike leg and its station (the far station can be 50 km away), or
 * for a trip without one the whole way of the train.
 */
export function trainTripBounds(
  trip: TrainTrip,
  option: TrainOption,
): maplibregl.LngLatBounds {
  const coords = (rideOf(trip, option)?.geometry.coordinates ??
    option.path ??
    option.stops.map(s => [s.lon, s.lat])) as [number, number][]
  return coords.reduce(
    (bounds, c) => bounds.extend(c),
    new maplibregl.LngLatBounds(coords[0], coords[0]),
  )
}
