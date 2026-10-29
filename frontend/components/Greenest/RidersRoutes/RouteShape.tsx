import { cx } from 'class-variance-authority'

type RouteShapeProps = {
  /** [lon, lat] points (a route's `preview`). */
  points: [number, number][]
  className?: string
}

const SIZE = 100
const PAD = 8

/** The route's shape as a small line drawing, north up, with a dot at the start. */
export default function RouteShape({ points, className }: RouteShapeProps) {
  if (points.length < 2) {
    return null
  }
  // Longitude degrees are shorter than latitude degrees this far north.
  const scaleX = Math.cos((points[0][1] * Math.PI) / 180)
  const xs = points.map(([lon]) => lon * scaleX)
  const ys = points.map(([, lat]) => lat)
  const [minX, maxX, minY, maxY] = [
    Math.min(...xs),
    Math.max(...xs),
    Math.min(...ys),
    Math.max(...ys),
  ]
  const span = Math.max(maxX - minX, maxY - minY) || 1
  const scale = (SIZE - 2 * PAD) / span
  // Centre the shape in the square.
  const offX = (SIZE - (maxX - minX) * scale) / 2
  const offY = (SIZE - (maxY - minY) * scale) / 2
  const xy = xs.map((x, i) => [
    offX + (x - minX) * scale,
    SIZE - offY - (ys[i] - minY) * scale,
  ])
  const path = xy
    .map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(' ')

  return (
    <svg
      aria-hidden
      className={cx('text-leaf-moss', className)}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
    >
      <path
        d={path}
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={3}
      />
      <circle
        cx={xy[0][0]}
        cy={xy[0][1]}
        fill="white"
        r={4}
        stroke="currentColor"
        strokeWidth={2.5}
      />
    </svg>
  )
}
