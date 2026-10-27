import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'

const STATS_URL = 'https://api.atrai.bike/collections/statistics/items'
const RESPONSE_HEADERS = {
  'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
} as const

const ttl = 15 * 60 * 1000
const cache = new TTLCache<string, unknown>({ ttl })

export const dynamic = 'force-dynamic'

export type WeeklyStatEntry = {
  week: string
  trip_count: number
  total_duration_s: number
  average_duration_s: number
  total_distance_m: number
  average_distance_m: number
  average_speed_kmh: number
  total_kcal: number
}

export type LatestStats = {
  trip_count: number
  total_duration_s: number
  average_duration_s: number
  total_distance_m: number
  average_distance_m: number
  average_speed_kmh: number
  total_kcal: number
}

export type TrafficStatsPayload = {
  latest_stats: LatestStats
  weekly_stats: WeeklyStatEntry[]
}

/**
 * Convert Python-dict string to valid JSON.
 * Handles: single-quoted strings, True/False/None → true/false/null.
 */
function pythonDictToJson(raw: string): string {
  return (
    raw
      // Unwrap numpy scalar wrappers, e.g. np.float64(123.4) -> 123.4
      .replace(/np\.(?:float64|float32|int64|int32)\(([^()]+)\)/g, '$1')
      // Replace single-quoted string values/keys with double-quoted ones.
      // This handles the majority of cases in this payload.
      .replace(/'/g, '"')
      // Python booleans / None
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false')
      .replace(/\bNone\b/g, 'null')
  )
}

function jsonResponse(data: unknown, init?: ResponseInit) {
  return NextResponse.json(data, {
    ...init,
    headers: {
      ...RESPONSE_HEADERS,
      ...init?.headers,
    },
  })
}

export const GET = async () => {
  const cacheKey = 'traffic-stats-heilbronn'

  if (cache.has(cacheKey)) {
    return jsonResponse(cache.get(cacheKey))
  }

  try {
    const response = await fetch(STATS_URL, { cache: 'no-store' })

    if (!response.ok) {
      throw new Error(`API error ${response.status}`)
    }

    const collection = await response.json()
    const feature = Array.isArray(collection?.features)
      ? collection.features.find(
          (item: { properties?: { tag?: string; statistics?: unknown } }) =>
            item?.properties?.tag === 'heilbronn' &&
            !!item?.properties?.statistics,
        ) ??
        collection.features.find(
          (item: { properties?: { statistics?: unknown } }) =>
            !!item?.properties?.statistics,
        )
      : undefined

    const rawStats = feature?.properties?.statistics

    if (!rawStats) {
      return jsonResponse(
        { error: 'No statistics field in response' },
        { status: 502 },
      )
    }

    const parsed = (
      typeof rawStats === 'string' ? JSON.parse(pythonDictToJson(rawStats)) : rawStats
    ) as Record<string, unknown> & {
      latest_stats: LatestStats
      weekly_stats?: WeeklyStatEntry[]
      periodic_stats?: WeeklyStatEntry[]
    }

    const payload: TrafficStatsPayload = {
      latest_stats: parsed.latest_stats,
      weekly_stats: parsed.weekly_stats ?? parsed.periodic_stats ?? [],
    }

    cache.set(cacheKey, payload)
    return jsonResponse(payload)
  } catch {
    return jsonResponse(
      { error: 'Failed to fetch traffic stats' },
      { status: 500 },
    )
  }
}
