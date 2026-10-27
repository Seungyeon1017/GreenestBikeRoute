import { useEffect, useMemo, useState } from 'react'
import type { SenseBox } from './useOpenSenseMap'

export type PMType = 'PM1' | 'PM25' | 'PM4' | 'PM10'

interface RawMeasurement {
  createdAt: string
  value: string
  sensorId: string
  boxId: string
}

export interface StationPM {
  boxId: string
  boxName: string
  coordinates: [number, number] // [lng, lat]
  measurements: Partial<Record<PMType, number>>
  updatedAt: string
}

/** Normalise sensor title to a PMType key */
function parsePMType(title: string): PMType | null {
  const t = title.toLowerCase().replace(/[^a-z0-9.]/g, '')
  if (t.includes('pm10') || t.includes('pm 10')) {
    return 'PM10'
  }
  if (t.includes('pm25') || t.includes('pm2.5') || t.includes('pm2,5')) {
    return 'PM25'
  }
  if (t.includes('pm4') || t.includes('pm 4')) {
    return 'PM4'
  }
  if (t.includes('pm1') && !t.includes('pm10')) {
    return 'PM1'
  }
  return null
}

// Time window to consider recent measurements (30 minutes)
const TWO_HOURS = 2 * 60 * 60 * 1000

export default function useParticulateMatter(grouptag: string) {
  const [boxes, setBoxes] = useState<SenseBox[]>([])
  const [measurements, setMeasurements] = useState<RawMeasurement[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!grouptag) {
      return
    }

    const fetchData = async () => {
      setIsLoading(true)
      try {
        const [boxRes, measRes] = await Promise.all([
          fetch(`/api/opensensemap?grouptag=${encodeURIComponent(grouptag)}`),
          fetch(
            `/api/opensensemap/bytag?grouptag=${encodeURIComponent(grouptag)}`,
          ),
        ])

        if (!boxRes.ok || !measRes.ok) {
          throw new Error('Failed to fetch')
        }

        const [boxData, measData] = await Promise.all([
          boxRes.json(),
          measRes.json(),
        ])

        setBoxes(boxData)
        setMeasurements(measData)
      } catch {
        // silently fail
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [grouptag])

  const stations = useMemo<StationPM[]>(() => {
    if (boxes.length === 0) {
      return []
    }

    const now = Date.now()

    // Build a sensorId → { boxId, pmType } lookup from boxes
    const sensorLookup = new Map<string, { boxId: string; pmType: PMType }>()
    for (const box of boxes) {
      for (const sensor of box.sensors) {
        const pmType = parsePMType(sensor.title)
        if (pmType) {
          sensorLookup.set(sensor._id, { boxId: box._id, pmType })
        }
      }
    }

    // Group recent measurements by boxId
    const boxMeasurements = new Map<
      string,
      { pm: Partial<Record<PMType, number>>; latest: string }
    >()

    for (const m of measurements) {
      const age = now - new Date(m.createdAt).getTime()
      console.log('AGE', age)
      console.log(new Date(now).toISOString())
      if (age > TWO_HOURS) {
        continue
      }

      const lookup = sensorLookup.get(m.sensorId)
      if (!lookup) {
        continue
      }

      const entry = boxMeasurements.get(lookup.boxId) ?? {
        pm: {},
        latest: m.createdAt,
      }
      entry.pm[lookup.pmType] = parseFloat(m.value)
      if (m.createdAt > entry.latest) {
        entry.latest = m.createdAt
      }
      boxMeasurements.set(lookup.boxId, entry)
    }

    // Merge with box metadata — include ALL boxes, even those without recent data
    return boxes.map(box => {
      const entry = boxMeasurements.get(box._id)
      return {
        boxId: box._id,
        boxName: box.name,
        coordinates: box.currentLocation.coordinates,
        measurements: entry?.pm ?? {},
        updatedAt: entry?.latest ?? box.updatedAt,
      }
    })
  }, [boxes, measurements])

  return { stations, isLoading }
}

// Debug: log summary to browser console to help troubleshoot missing data
// (will only run in the browser since this is a client hook)
// eslint-disable-next-line no-console
export const _debug_particulate_matter = (
  boxes: SenseBox[] = [],
  measurements: RawMeasurement[] = [],
) => {
  try {
    if (typeof window === 'undefined') {
      return
    }

    const measCount = measurements.length
    const boxCount = boxes.length
    const latest = measurements.reduce(
      (acc, m) => {
        return acc && acc > m.createdAt ? acc : m.createdAt
      },
      measurements.length ? measurements[0].createdAt : null,
    )

    // eslint-disable-next-line no-console
    console.debug('PM hook debug', { boxCount, measCount, latest })
  } catch (e) {
    // ignore
  }
}
