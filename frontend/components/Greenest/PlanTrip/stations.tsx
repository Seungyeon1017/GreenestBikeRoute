import { TrainFront } from 'lucide-react'
import type { TransitStopFeature } from '@/types/greenest'
import { SBAHN_COLOR, stationKind, TRAIN_COLOR } from './transitLayers'

/** For name search: case, accents and umlauts don't matter (Sülmertor = sulmertor). */
function folded(text: string) {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

/** Stations whose name contains `query`; a word starting with it first, then by name. */
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
    .map(s => ({ s, name: folded(s.properties.name) }))
    .filter(({ name }) => name.includes(q))
    .sort(
      (a, b) =>
        Number(starts(b.name)) - Number(starts(a.name)) ||
        a.name.localeCompare(b.name),
    )
    .slice(0, max)
    .map(({ s }) => s)
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
