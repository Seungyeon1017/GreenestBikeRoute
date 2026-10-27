import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'

const BOXES_URL = 'https://api.opensensemap.org/boxes'
const STATS_URL = 'https://api.opensensemap.org/statistics/descriptive'

const ttl = 1 * 60 * 1000 // 1 minute

const cache = new TTLCache<string, unknown>({ ttl })

interface OsmBox {
  _id: string
  sensors: Array<{ _id: string; title: string }>
}

interface RawMeasurement {
  sensorId: string
  boxId: string
  createdAt: string
  value: string
}

// RFC3339 timestamp keys returned by the statistics/descriptive endpoint
const TIMESTAMP_KEY_RE = /^\d{4}-\d{2}-\d{2}T/

export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const grouptag = searchParams.get('grouptag')

  if (!grouptag) {
    return NextResponse.json(
      { error: 'Missing grouptag parameter' },
      { status: 400 },
    )
  }

  const cacheKey = `opensensemap-bytag-${grouptag}`

  if (cache.has(cacheKey)) {
    return NextResponse.json(cache.get(cacheKey))
  }

  try {
    // Step 1: Get boxes for this grouptag to obtain IDs and sensor phenomena
    const boxesRes = await fetch(
      `${BOXES_URL}?grouptag=${encodeURIComponent(grouptag)}&format=json`,
    )
    if (!boxesRes.ok) {
      throw new Error(`Boxes API failed: ${boxesRes.status}`)
    }
    const boxes: OsmBox[] = await boxesRes.json()

    if (!Array.isArray(boxes) || boxes.length === 0) {
      cache.set(cacheKey, [])
      return NextResponse.json([])
    }

    // Step 2: Collect box IDs and unique sensor phenomena
    const boxIds = boxes.map(b => b._id).join(',')
    const phenomena = new Set<string>()
    for (const box of boxes) {
      for (const sensor of box.sensors ?? []) {
        if (sensor.title) {
          phenomena.add(sensor.title)
        }
      }
    }

    // Step 3: Query statistics/descriptive for each phenomenon over the last 10 minutes
    const toDate = new Date()
    const fromDate = new Date(toDate.getTime() - 10 * 60 * 1000)

    const statsRequests = Array.from(phenomena).map(async phenomenon => {
      const params = new URLSearchParams({
        boxId: boxIds,
        phenomenon,
        'from-date': fromDate.toISOString(),
        'to-date': toDate.toISOString(),
        operation: 'arithmeticMean',
        window: '10m',
        format: 'json',
        columns: 'boxId',
      })
      const res = await fetch(`${STATS_URL}?${params}`)
      if (!res.ok) {
        return []
      }
      const data: unknown = await res.json()
      return Array.isArray(data) ? data : []
    })

    const statsResults = await Promise.all(statsRequests)

    // Step 4: Flatten statistics entries into RawMeasurement-compatible records.
    // The statistics JSON format is: [{ sensorId, boxId, "<ISO-timestamp>": <mean> }, ...]
    const nowStr = toDate.toISOString()
    const measurements: RawMeasurement[] = []

    for (const sensorList of statsResults) {
      for (const entry of sensorList as Record<string, unknown>[]) {
        if (!entry.sensorId || !entry.boxId) {
          continue
        }

        // Find the RFC3339 timestamp key that holds the arithmetic mean
        let value: string | null = null
        for (const [key, val] of Object.entries(entry)) {
          if (TIMESTAMP_KEY_RE.test(key) && val !== null && val !== undefined) {
            value = String(val)
            break
          }
        }
        if (value === null) {
          continue
        }

        measurements.push({
          sensorId: String(entry.sensorId),
          boxId: String(entry.boxId),
          createdAt: nowStr,
          value,
        })
      }
    }

    cache.set(cacheKey, measurements)
    return NextResponse.json(measurements)
  } catch {
    return NextResponse.json(
      { error: 'Failed to fetch openSenseMap measurement data' },
      { status: 500 },
    )
  }
}
