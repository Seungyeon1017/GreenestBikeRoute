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
// The swatches on the white panel are a little stronger, or they look washed out.
const AIR_LEGEND_OPACITY = 0.55
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
// Dimly lit: halfway between lit and dark.
const DIM = '#8f7a2e'
// Between two of the colours above, for the finer classes.
const SUNNY_HALF = '#cca05b'
const SHADED_HALF = '#606e96'
const DIM_DARK = '#615e41'
const DIM_LIT = '#bc961b'

// Classes, worst first as stepColor wants them; a legend shows them best first.
// Fine-grained like Plan a trip's hill bands: one swatch per class, exactly the
// colours on the map.
const STOP_GO_STEPS = [
  { color: GREEN, max: 0.4, key: 'free' },
  { color: LIME, max: 0.5, label: '0.4–0.5' },
  { color: YELLOW, max: 0.6, label: '0.5–0.6' },
  { color: ORANGE, max: 0.8, label: '0.6–0.8' },
  { color: RED, max: Infinity, key: 'stopping' },
]
const SPEED_STEPS = [
  { color: RED, max: 8, key: 'slow' },
  { color: ORANGE, max: 11, label: '8–11 km/h' },
  { color: YELLOW, max: 14, label: '11–14 km/h' },
  { color: LIME, max: 17, label: '14–17 km/h' },
  { color: GREEN, max: Infinity, key: 'fast' },
]
const SHADE_STEPS = [
  { color: SUNNY, max: 0.2, key: 'sunny' },
  { color: SUNNY_HALF, max: 0.4, label: '20–40 %' },
  { color: HALF_SHADED, max: 0.6, label: '40–60 %' },
  { color: SHADED_HALF, max: 0.8, label: '60–80 %' },
  { color: SHADED, max: Infinity, key: 'shaded' },
]
// Where a street is on the lighting axis (LIGHTING_LEVEL): its chance of being
// lit, with lit streets sliding down to dimly lit as fewer lamps were seen.
const LIGHTING_STEPS = [
  { color: DARK_STREET, max: 0.25, key: 'dark' },
  { color: DIM_DARK, max: 0.5, key: 'unlikely' },
  { color: DIM, max: 0.65, key: 'dim' },
  { color: DIM_LIT, max: 0.9, key: 'fewer' },
  { color: LIT, max: Infinity, key: 'lit' },
]

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
// lit (routing.lighting DIM_LIGHTS_PER_100M), drawn in DIM.
const DIM_LIGHTS_PER_100M = 1

const IS_NUMBER = (key: string) => ['==', ['typeof', ['get', key]], 'number']

// No lighting data, or nothing known about the street (chance exactly 0.5, see
// routing/lighting.py): grey, off the axis.
const UNKNOWN_LIGHTING = [
  'any',
  ['!', IS_NUMBER('lit')],
  ['==', ['get', 'lit'], 0.5],
]

// Where on the lighting axis a street is: its chance of being lit (0 dark to 1
// lit), but a lit street where Mapillary saw fewer lamps than
// DIM_LIGHTS_PER_100M slides from lit (1) down to dimly lit (0.5) as the lamps
// get fewer.
const LIGHTING_LEVEL = [
  'case',
  ['<', ['get', 'lit'], 0.5],
  ['get', 'lit'],
  IS_NUMBER('lights_per_100m'),
  [
    '+',
    0.5,
    ['*', 0.5, ['min', 1, ['/', ['get', 'lights_per_100m'], DIM_LIGHTS_PER_100M]]],
  ],
  ['get', 'lit'],
]

/** MapLibre `step` expression from legend steps with an upper bound per class. */
export function stepColor(
  property: string,
  steps: Array<{ color: string; max: number }>,
) {
  return stepOf(['get', property], steps)
}

/** Same for any expression, e.g. a computed value. */
function stepOf(value: unknown, steps: Array<{ color: string; max: number }>) {
  const expression: unknown[] = ['step', value, steps[0].color]
  steps.slice(1).forEach((step, i) => {
    expression.push(steps[i].max, step.color)
  })
  return expression as never
}

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
      'line-color': stepColor('stop_go', STOP_GO_STEPS),
      'line-width': LINE_WIDTH,
    },
  },
  speed: {
    type: 'line',
    paint: {
      'line-color': stepColor('speed_kmh', SPEED_STEPS),
      'line-width': LINE_WIDTH,
    },
  },
  shade: {
    type: 'line',
    paint: {
      'line-color': stepColor('shade', SHADE_STEPS),
      'line-width': LINE_WIDTH,
    },
  },
  lighting: {
    type: 'line',
    paint: {
      'line-color': [
        'case',
        UNKNOWN_LIGHTING,
        UNKNOWN_LIT,
        stepOf(LIGHTING_LEVEL, LIGHTING_STEPS),
      ] as never,
      'line-width': LINE_WIDTH,
    },
  },
}

type LegendStep = { color: string; label?: string; key?: string }

/** Swatches of the classes, in the order given. */
const legendOf = (steps: LegendStep[], opacity?: number) =>
  steps.map(({ color, label, key }) => ({ color, label, key, opacity }))

/** The classes best first, for steps that are listed worst first. */
const bestFirst = (steps: LegendStep[]) => [...steps].reverse()

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
    legend: legendOf(PM_RISK_STEPS, AIR_LEGEND_OPACITY),
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
    legend: legendOf(STOP_GO_STEPS),
  },
  {
    id: 'speed',
    colorsStreets: true,
    overlay: 'speed',
    source: 'ATRAI senseBox:bike (speed_map)',
    availability: 'measured',
    legend: legendOf(bestFirst(SPEED_STEPS)),
  },
  {
    id: 'shade',
    colorsStreets: true,
    overlay: 'shade',
    source: 'LGL BW LoD2, Stadt Heilbronn Baumkataster (dl-de/by-2-0)',
    availability: 'estimated',
    legend: legendOf(bestFirst(SHADE_STEPS)),
  },
  {
    id: 'lighting',
    colorsStreets: true,
    overlay: 'lighting',
    source:
      'OpenStreetMap (ODbL), Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0)',
    availability: 'estimated',
    legend: [
      ...legendOf(bestFirst(LIGHTING_STEPS)),
      { color: UNKNOWN_LIT, key: 'unknown' },
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
