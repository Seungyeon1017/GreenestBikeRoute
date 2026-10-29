import type { ExpressionSpecification } from 'maplibre-gl'

/**
 * Hill colours by grade in the riding direction (%; negative = downhill), in
 * bands so a colour on the map can be looked up in the legend. Uphill runs
 * green → yellow → orange → red with one band per percent up to 4 % (2–4 %
 * already feels like work), then wider bands because steep streets are rare,
 * ending in dark red for 10 % and more. Downhill is cool and light: pale blue
 * to soft violet, the steeper the more braking. Each band starts at `from` and runs to the next one.
 */
export const GRADE_BANDS: Array<{ from: number; color: string }> = [
  // Downhill is the easy part, so its colours stay light like the flat green.
  { from: -Infinity, color: '#8b5cf6' },
  { from: -10, color: '#a78bfa' },
  { from: -6, color: '#8fa6f2' },
  { from: -4, color: '#7cc4ec' },
  { from: -2, color: '#a8daf2' },
  { from: -1, color: '#8fbf6a' },
  { from: 1, color: '#c3cf3c' },
  { from: 2, color: '#f2c230' },
  { from: 3, color: '#f59e0b' },
  { from: 4, color: '#ea6a0c' },
  { from: 6, color: '#dc2626' },
  { from: 10, color: '#7f1d1d' },
]

/** MapLibre line colour from a feature's `grade_pct`: the band it falls in. */
export const GRADE_COLOR: ExpressionSpecification = [
  'step',
  ['get', 'grade_pct'],
  GRADE_BANDS[0].color,
  ...GRADE_BANDS.slice(1).flatMap(({ from, color }) => [from, color]),
]
