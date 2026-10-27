import type { EnvironmentLayer } from '@/types/greenest'

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

export const CYCLE_LANE_COLOR = '#0d9488'

const legendOf = (steps: Array<{ color: string; label: string }>) =>
  steps.map(({ color, label }) => ({ color, label }))

export const ENVIRONMENT_LAYERS: EnvironmentLayer[] = [
  {
    id: 'air-quality',
    unit: 'risk index 0–1',
    source: 'ATRAI senseBox:bike (danger_zones_PM)',
    availability: 'measured',
    legend: legendOf(PM_RISK_STEPS),
  },
  {
    id: 'cycling-infrastructure',
    unit: 'roughness 0–100',
    source: 'ATRAI senseBox:bike (bumpy_roads), OpenStreetMap',
    availability: 'measured',
    legend: [
      ...legendOf(ROUGHNESS_STEPS),
      { color: CYCLE_LANE_COLOR, label: 'cycle lane (OSM)' },
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
  {
    id: 'environmental-score',
    unit: '0–100',
    availability: 'unavailable',
    legend: [],
  },
]
