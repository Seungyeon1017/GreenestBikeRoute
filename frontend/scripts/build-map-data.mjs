#!/usr/bin/env node
/**
 * Turns the ATRAI datasets in ../data (downloaded by ../download_data.py)
 * into small GeoJSON files for the Overview map in public/data/.
 *
 *   node scripts/build-map-data.mjs
 *
 * Only measured values are aggregated; areas without measurements get null,
 * never an estimate. Run it again after downloading new data.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const DATA_DIR = join(here, '..', '..', 'data')
const OUT_DIR = join(here, '..', 'public', 'data')

// Grid used as "area" on the Overview map: ~500 m x 500 m cells.
const CELL_M = 500
const LAT0 = 49.14
const DLAT = CELL_M / 111320
const DLON = CELL_M / (111320 * Math.cos((LAT0 * Math.PI) / 180))
// Cells need at least this many measurement points to report a mean.
const MIN_POINTS = 5

const load = name =>
  JSON.parse(readFileSync(join(DATA_DIR, `${name}_heilbronn.geojson`), 'utf8'))
    .features

const round = (value, digits) => {
  const f = 10 ** digits
  return Math.round(value * f) / f
}
const roundCoords = coords => coords.map(([x, y]) => [round(x, 5), round(y, 5)])

// The street network defines the study area; rides outside it are dropped.
const roads = load('road_network')
let bbox = [Infinity, Infinity, -Infinity, -Infinity]
for (const f of roads) {
  for (const [x, y] of f.geometry.coordinates) {
    bbox = [
      Math.min(bbox[0], x),
      Math.min(bbox[1], y),
      Math.max(bbox[2], x),
      Math.max(bbox[3], y),
    ]
  }
}
const inArea = ([x, y]) =>
  x >= bbox[0] && x <= bbox[2] && y >= bbox[1] && y <= bbox[3]

const cells = new Map()
const cellKey = ([x, y]) =>
  `${Math.floor((x - bbox[0]) / DLON)}:${Math.floor((y - bbox[1]) / DLAT)}`
const cellFor = point => {
  const key = cellKey(point)
  if (!cells.has(key)) {
    cells.set(key, {
      pmSum: 0,
      pmCount: 0,
      overtakingSum: 0,
      overtakingCount: 0,
      roughSum: 0,
      roughLength: 0,
    })
  }
  return cells.get(key)
}

const lengthM = coords => {
  let sum = 0
  for (let i = 1; i < coords.length; i++) {
    const [x1, y1] = coords[i - 1]
    const [x2, y2] = coords[i]
    const dx = (x2 - x1) * 111320 * Math.cos((y1 * Math.PI) / 180)
    const dy = (y2 - y1) * 111320
    sum += Math.hypot(dx, dy)
  }
  return sum
}

// Traffic + fine-dust risk index per measurement point (0 = low, 1 = high).
for (const f of load('danger_zones_PM')) {
  const p = f.geometry.coordinates
  const risk = f.properties['Risk Index']
  if (risk == null || !inArea(p)) {
    continue
  }
  const cell = cellFor(p)
  cell.pmSum += risk
  cell.pmCount += 1
}

// Overtaking risk index per measured overtaking manoeuvre (0..1).
for (const f of load('danger_zones')) {
  const p = f.geometry.coordinates
  const risk = f.properties['Risk Index Overtaking']
  if (risk == null || !inArea(p)) {
    continue
  }
  const cell = cellFor(p)
  cell.overtakingSum += risk
  cell.overtakingCount += 1
}

// Measured surface roughness (0..100), assigned to the cell of each segment's midpoint.
const roughFeatures = []
for (const f of load('bumpy_roads')) {
  const coords = f.geometry.coordinates
  const roughness = f.properties['Normalized Roughness']
  if (roughness == null || !inArea(coords[0])) {
    continue
  }
  const length = lengthM(coords)
  const mid = coords[Math.floor(coords.length / 2)]
  const cell = cellFor(mid)
  cell.roughSum += roughness * length
  cell.roughLength += length
  roughFeatures.push({
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: roundCoords(coords) },
    properties: { roughness: round(roughness, 1), name: f.properties.name },
  })
}

// Streets tagged with a cycle lane in OpenStreetMap.
const LANE_TAGS = new Set(['lane', 'shared_lane', 'opposite_lane', 'opposite'])
const laneFeatures = load('bike_road_network')
  .filter(f => LANE_TAGS.has(f.properties.cycleway))
  .map(f => ({
    type: 'Feature',
    geometry: {
      type: 'LineString',
      coordinates: roundCoords(f.geometry.coordinates),
    },
    properties: { cycleway: f.properties.cycleway, name: f.properties.name },
  }))

const areaFeatures = []
for (const [key, c] of cells) {
  const [i, j] = key.split(':').map(Number)
  const x0 = bbox[0] + i * DLON
  const y0 = bbox[1] + j * DLAT
  const pm = c.pmCount >= MIN_POINTS ? c.pmSum / c.pmCount : null
  const overtaking =
    c.overtakingCount >= MIN_POINTS ? c.overtakingSum / c.overtakingCount : null
  const roughness = c.roughLength > 0 ? c.roughSum / c.roughLength : null
  if (pm == null && overtaking == null && roughness == null) {
    continue
  }
  areaFeatures.push({
    type: 'Feature',
    id: areaFeatures.length,
    geometry: {
      type: 'Polygon',
      coordinates: [
        roundCoords([
          [x0, y0],
          [x0 + DLON, y0],
          [x0 + DLON, y0 + DLAT],
          [x0, y0 + DLAT],
          [x0, y0],
        ]),
      ],
    },
    properties: {
      cell: key,
      pm_risk: pm == null ? null : round(pm, 3),
      pm_points: c.pmCount,
      overtaking_risk: overtaking == null ? null : round(overtaking, 3),
      overtaking_points: c.overtakingCount,
      roughness: roughness == null ? null : round(roughness, 1),
      roughness_measured_m: Math.round(c.roughLength),
    },
  })
}

const write = (name, features) => {
  const path = join(OUT_DIR, name)
  writeFileSync(path, JSON.stringify({ type: 'FeatureCollection', features }))
  // eslint-disable-next-line no-console
  console.log(`${name}: ${features.length} features`)
}

mkdirSync(OUT_DIR, { recursive: true })
write('areas.geojson', areaFeatures)
write('surface-roughness.geojson', roughFeatures)
write('cycle-lanes.geojson', laneFeatures)
writeFileSync(
  join(OUT_DIR, 'meta.json'),
  JSON.stringify(
    {
      generatedAt: new Date().toISOString(),
      source:
        'ATRAI senseBox:bike, Heilbronn campaign (api.atrai.bike); OpenStreetMap',
      cellSizeM: CELL_M,
      minPointsPerCell: MIN_POINTS,
      bbox: bbox.map(v => round(v, 5)),
    },
    null,
    2,
  ),
)
