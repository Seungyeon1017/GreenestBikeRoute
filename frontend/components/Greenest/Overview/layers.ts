import type {
  CircleLayerSpecification,
  LineLayerSpecification,
} from 'maplibre-gl'
import type { EnvironmentLayer, EnvironmentLayerId } from '@/types/greenest'
import { SHADE_HOUR } from '@/hooks/useOverlays'

/**
 * Environmental layers on the Overview map. Labels and descriptions live in
 * messages/*.json under `greenest.layers.<id>`.
 *
 * Layers without a connected dataset stay `unavailable`: they can't be turned
 * on and never show values.
 */

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
      'line-color': ramp(
        'score',
        0,
        RED,
        25,
        ORANGE,
        50,
        YELLOW,
        75,
        LIME,
        100,
        GREEN,
      ),
      'line-width': LINE_WIDTH,
    },
  },
  'bike-friendly': {
    type: 'line',
    paint: { 'line-color': '#0f766e', 'line-width': LINE_WIDTH },
  },
  overtaking: {
    type: 'circle',
    paint: {
      'circle-color': '#7b1fa2',
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
      'line-color': ramp('shade', 0, '#f59e0b', 0.5, '#a3a3a3', 1, '#1e3a8a'),
      'line-width': LINE_WIDTH,
    },
  },
  lighting: {
    type: 'line',
    paint: {
      'line-color': ramp('lit', 0, '#334155', 0.5, '#94a3b8', 1, '#eab308'),
      'line-width': LINE_WIDTH,
    },
  },
}

const legendOf = (steps: Array<{ color: string; label: string }>) =>
  steps.map(({ color, label }) => ({ color, label }))

export const ENVIRONMENT_LAYERS: EnvironmentLayer[] = [
  {
    id: 'environmental-score',
    colorsStreets: true,
    overlay: 'score',
    unit: 'score 0–100 (higher = better)',
    source: 'GreenestBikeRoute routing: ATRAI senseBox:bike, OpenStreetMap',
    availability: 'measured',
    legend: [
      { color: GREEN, label: '75–100 (best quarter)' },
      { color: LIME, label: '50–75' },
      { color: YELLOW, label: '25–50' },
      { color: RED, label: '0–25 (worst quarter)' },
    ],
  },
  {
    id: 'air-quality',
    unit: 'risk index 0–1',
    source: 'ATRAI senseBox:bike (danger_zones_PM)',
    availability: 'measured',
    legend: legendOf(PM_RISK_STEPS),
  },
  {
    id: 'surface-roughness',
    colorsStreets: true,
    unit: 'roughness 0–100',
    source: 'ATRAI senseBox:bike (bumpy_roads)',
    availability: 'measured',
    legend: legendOf(ROUGHNESS_STEPS),
  },
  {
    id: 'bike-friendly',
    colorsStreets: true,
    overlay: 'bike-friendly-streets',
    source: 'OpenStreetMap contributors (ODbL)',
    availability: 'mapped',
    legend: [
      {
        color: '#0f766e',
        label: 'bike path or lane, way open to bikes, or bike route',
      },
    ],
  },
  {
    id: 'overtaking',
    overlay: 'danger',
    unit: 'risk index 0–1',
    source: 'ATRAI senseBox:bike (danger_zones_raw, overtakes over 25 cm)',
    availability: 'measured',
    legend: [{ color: '#7b1fa2', label: 'close overtake (darker = riskier)' }],
  },
  {
    id: 'stop-and-go',
    colorsStreets: true,
    overlay: 'flow',
    unit: 'stop-and-go 0–1',
    source: 'ATRAI senseBox:bike (traffic_flow)',
    availability: 'measured',
    legend: [
      { color: GREEN, label: '0.4 or less (rolls freely)' },
      { color: YELLOW, label: '0.6' },
      { color: RED, label: '0.8 or more (much stopping)' },
    ],
  },
  {
    id: 'speed',
    colorsStreets: true,
    overlay: 'speed',
    unit: 'km/h',
    source: 'ATRAI senseBox:bike (speed_map)',
    availability: 'measured',
    legend: [
      { color: GREEN, label: '20 km/h or more' },
      { color: YELLOW, label: '14 km/h' },
      { color: RED, label: '8 km/h or less' },
    ],
  },
  {
    id: 'shade',
    colorsStreets: true,
    overlay: 'shade',
    unit: `share in shade, ${SHADE_HOUR}:00 on 21 July`,
    source: 'LGL BW LoD2, Stadt Heilbronn Baumkataster (dl-de/by-2-0)',
    availability: 'estimated',
    legend: [
      { color: '#1e3a8a', label: 'mostly shaded' },
      { color: '#a3a3a3', label: 'half' },
      { color: '#f59e0b', label: 'mostly sunny' },
    ],
  },
  {
    id: 'lighting',
    colorsStreets: true,
    overlay: 'lighting',
    unit: 'chance the street is lit 0–1',
    source:
      'OpenStreetMap (ODbL), Mapillary (CC BY-SA 4.0), LGL BW LoD2 (dl-de/by-2-0)',
    availability: 'estimated',
    legend: [
      { color: '#eab308', label: 'probably lit' },
      { color: '#94a3b8', label: 'unknown' },
      { color: '#334155', label: 'probably dark' },
    ],
  },
  {
    id: 'noise',
    unit: 'dB(A)',
    availability: 'unavailable',
    legend: [],
  },
  {
    id: 'green-spaces',
    unit: '% green cover',
    availability: 'unavailable',
    legend: [],
  },
]
