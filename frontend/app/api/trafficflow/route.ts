import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'

const TRAFFIC_FLOW_URL =
  'https://api.atrai.bike/collections/speed_map_heilbronn/items?limit=0'

const ttl = 15 * 60 * 1000 // 15 minutes
const cache = new TTLCache<string, unknown>({ ttl })

export const GET = async () => {
  const cacheKey = 'traffic-flow-heilbronn'

  if (cache.has(cacheKey)) {
    return NextResponse.json(cache.get(cacheKey))
  }

  try {
    const response = await fetch(TRAFFIC_FLOW_URL)

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`)
    }

    const data = await response.json()

    if (
      !data ||
      data.type !== 'FeatureCollection' ||
      !Array.isArray(data.features)
    ) {
      return NextResponse.json(
        { error: 'Invalid traffic flow response format' },
        { status: 502 },
      )
    }

    cache.set(cacheKey, data)
    return NextResponse.json(data)
  } catch {
    return NextResponse.json(
      { error: 'Failed to fetch traffic flow data' },
      { status: 500 },
    )
  }
}
