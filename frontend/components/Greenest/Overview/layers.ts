import type {
  CircleLayerSpecification,
  LineLayerSpecification,
} from 'maplibre-gl'
import type { EnvironmentLayer, EnvironmentLayerId } from '@/types/greenest'

/**
 * Environmental layers on the Overview map. Labels and descriptions live in
 * messages/*.json under `greenest.layers.<id>`.
 *
 * Layers without a connected dataset stay `unavailable`: they can't be turned
 * on and never show values.
 */

/** How opaque the air-quality cells and the roughness lines are drawn; their legends' swatches match. */
export const AIR_OPACITY = 0.4
const ROUGHNESS_OPACITY = 0.85

// Breaks follow the spread of the Heilbronn cells (roughly quintiles), so the
// colours show relative differences within the city.
export const PM_RISK_STEPS = [
  { color: '#22c55e', max: 0.29, label: '< 0.29' },
  { color: '#84cc16', max: 0.32, label: '0.29–0.32' },
  { color: '#eab308', max: 0.33, label: '0.32–0.33' },
  { color: '#f97316', max: 0.35, label: '0.33–0.35' },
  { color: '#ef4444', max: Infinity, label: '> 0.35' },
]

// Same classes as the routing demo (demo-prototype/index.html).
export const ROUGHNESS_STEPS = [
  { color: '#4caf50', max: 10, label: '< 10' },
  { color: '#f2c94c', max: 20, label: '10–20' },
  { color: '#f2994a', max: 30, label: '20–30' },
  { color: '#d63b3b', max: Infinity, label: '30+' },
]

// Colours for the backend overlays, from bad (red) to good (green).
const RED = '#d63b3b'
const ORANGE = '#f2994a'
const YELLOW = '#f2c94c'
const LIME = '#84cc16'
const GREEN = '#16a34a'

// Overall score classes, worst first as stepColor wants them; the legend shows
// them best first. Real scores fall between about 30 and 100.
const SCORE_STEPS = [
  { color: RED, max: 30 },
  { color: ORANGE, max: 45 },
  { color: YELLOW, max: 65 },
  { color: LIME, max: 85 },
  { color: GREEN, max: Infinity },
]

// Colours that the map and a legend both use.
const BIKE_PATH = '#0f766e'
const OVERTAKING = '#7b1fa2'
const SHADED = '#1e3a8a'
const HALF_SHADED = '#a3a3a3'
const SUNNY = '#f59e0b'
const LIT = '#eab308'
const UNKNOWN_LIT = '#94a3b8'
const DARK_STREET = '#334155'

/** Line width that grows when zooming in. */
const LINE_WIDTH = [
  'interpolate',
  ['linear'],
  ['zoom'],
  12,
  1.2,
  16,
  4,
] as never

// Lit streets where Mapillary saw fewer lights per 100 m than this are dimly
// lit (routing.lighting DIM_LIGHTS_PER_100M). Drawn halfway between lit
// (#eab308) and dark (#334155).
const DIM_LIGHTS_PER_100M = 1
const DIM = '#8f7a2e'

/** MapLibre `step` expression from legend steps with an upper bound per class. */
export function stepColor(
  property: string,
  steps: Array<{ color: string; max: number }>,
) {
  const expression: unknown[] = ['step', ['get', property], steps[0].color]
  steps.slice(1).forEach((step, i) => {
    expression.push(steps[i].max, step.color)
  })
  return expression as never
}

/** Colour along a value range, e.g. [0, RED, 100, GREEN]. */
const ramp = (property: string, ...stops: Array<number | string>) =>
  ['interpolate', ['linear'], ['get', property], ...stops] as never

/**
 * How each backend overlay is drawn. Every overlay is one MapLibre layer with
 * the same id as its EnvironmentLayer.
 */
export const OVERLAY_STYLES: Partial<
  Record<
    EnvironmentLayerId,
    | { type: 'line'; paint: LineLayerSpecification['paint'] }
    | { type: 'circle'; paint: CircleLayerSpecification['paint'] }
  >
> = {
  'environmental-score': {
    type: 'line',
    paint: {
      'line-color': stepColor('score', SCORE_STEPS),
      'line-width': LINE_WIDTH,
      // Streets no sensor bike rode: scored from OpenStreetMap and nearby air only.
      'line-opacity': ['case', ['get', 'ridden'], 1, 0.4] as never,
    },
  },
  'surface-roughness': {
    type: 'line',
    paint: {
      'line-color': stepColor('roughness', ROUGHNESS_STEPS),
      'line-width': [
        'interpolate',
        ['linear'],
        ['zoom'],
        12,
        1.5,
        16,
        4,
      ] as never,
      'line-opacity': ROUGHNESS_OPACITY,
    },
  },
  'bike-friendly': {
    type: 'line',
    paint: { 'line-color': BIKE_PATH, 'line-width': LINE_WIDTH },
  },
  overtaking: {
    type: 'circle',
    paint: {
      'circle-color': OVERTAKING,
      'circle-radius': [
        'interpolate',
        ['linear'],
        ['zoom'],
        12,
        2,
        16,
        5,
      ] as never,
      'circle-opacity': ['+', 0.2, ['*', 0.6, ['get', 'risk']]] as never,
    },
  },
  'stop-and-go': {
    type: 'line',
    paint: {
      'line-color': ramp('stop_go', 0.4, GREEN, 0.6, YELLOW, 0.8, RED),
      'line-width': LINE_WIDTH,
    },
  },
  speed: {
    type: 'line',
    paint: {
      'line-color': ramp('speed_kmh', 8, RED, 14, YELLOW, 20, GREEN),
      'line-width': LINE_WIDTH,
    },
  },
  shade: {
    type: 'line',
    paint: {
      'line-color': ramp('shade', 0, SUNNY, 0.5, HALF_SHADED, 1, SHADED),
      'line-width': LINE_WIDTH,
    },
  },
  lighting: {
    type: 'line',
    paint: {
      'line-color': [
        'case',
        [
          'all',
          ['has', 'lights_per_100m'],
          ['>=', ['get', 'lit'], 0.5],
          ['<', ['get', 'lights_per_100m'], DIM_LIGHTS_PER_100M],
        ],
        DIM,
        ramp('lit', 0, DARK_STREET, 0.5, UNKNOWN_LIT, 1, LIT),
      ] as never,
      'line-width': LINE_WIDTH,
    },
  },
}

const legendOf = (
  steps: Array<{ color: string; label: string }>,
  opacity?: number,
) => steps.map(({ color, label }) => ({ color, label, opacity }))

export const ENVIRONMENT_LAYERS: EnvironmentLayer[] = [
  {
    id: 'environmental-score',
    colorsStreets: true,
    overlay: 'score',
    source: 'GreenestBikeRoute: ATRAI senseBox:bike, OpenStreetMap',
    availability: 'measured',
    legend: [
      { color: GREEN, key: 'top' },
      { color: LIME, label: '65–85' },
      { color: YELLOW, label: '45–65' },
      { color: ORANGE, label: '30–45' },
      { color: RED, label: '< 30' },
      { color: `${GREEN}66`, key: 'faded' },
    ],
  },
  {
    id: 'air-quality',
    source: 'ATRAI senseBox:bike (danger_zones_PM)',
    availability: 'measured',
    legend: legendOf(PM_RISK_STEPS, AIR_OPACITY),
  },
  {
    id: 'surface-roughness',
    colorsStreets: true,
    overlay: 'roughness',
    source: 'ATRAI senseBox:bike (bumpy_roads)',
    availability: 'measured',
    legend: legendOf(ROUGHNESS_STEPS, ROUGHNESS_OPACITY),
  },
  {
    id: 'bike-friendly',
    colorsStreets: true,
    overlay: 'bike-friendly-streets',
    source: 'OpenStreetMap contributors (ODbL)',
    availability: 'mapped',
    legend: [{ color: BIKE_PATH, key: 'path' }],
  },
  {
    id: 'overtaking',
    overlay: 'danger',
    source: 'ATRAI senseBox:bike (danger_zones_raw, overtakes over 25 cm)',
    availability: 'measured',
    legend: [{ color: OVERTAKING, key: 'close' }],
  },
  {
    id: 'stop-and-go',
    colorsStreets: true,
    overlay: 'flow',
    source: 'ATRAI senseBox:bike (traffic_flow)',
    availability: 'measured',
    legend: [
      { color: GREEN, key: 'free' },
      { color: YELLOW, label: '0.6' },
      { color: RED, key: 'stopping' },
    ],
  },
  {
    id: 'speed',
    colorsStreets: true,
    overlay: 'speed',
    source: 'ATRAI senseBox:bike (speed_map)',
    availability: 'measured',
    legend: [
      { color: GREEN, key: 'fast' },
      { color: YELLOW, label: '14 km/h' },
      { color: RED, key: 'slow' },
    ],
  },
  {
    id: 'shade',
    colorsStreets: true,
    overlay: 'shade',
    source: 'LGL BW LoD2, Stadt Heilbronn Baumkataster (dl-de/by-2-0)',
    availability: 'estimated',
    legend: [
      { color: SHADED, key: 'shaded' },
      { color: HALF_SHADED, key: 'half' },
      { color: SUNNY, key: 'sunny' },
    ],
  },
  {
    id: 'lighting',
    colorsStreets: true,
    overlay: 'lighting',
    source:
      'OpenStreetMap (ODbL), Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0)',
    availability: 'estimated',
    legend: [
      { color: LIT, key: 'lit' },
      { color: DIM, key: 'dim' },
      { color: UNKNOWN_LIT, key: 'unknown' },
      { color: DARK_STREET, key: 'dark' },
    ],
  },
  {
    id: 'noise',
    availability: 'unavailable',
    legend: [],
  },
  {
    id: 'green-spaces',
    availability: 'unavailable',
    legend: [],
  },
]
