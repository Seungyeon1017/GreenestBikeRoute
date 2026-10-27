import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'

const BASE_URL = 'https://wiediversistmeingarten.org/api/station'

const ttl = 15 * 60 * 1000 // 15 minutes

const birdCache = new TTLCache<string, any>({ ttl })

export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const stationId = searchParams.get('stationId')

  if (!stationId) {
    return NextResponse.json(
      { error: 'Missing stationId parameter' },
      { status: 400 },
    )
  }

  const cacheKey = `birdiary-${stationId}`

  if (birdCache.has(cacheKey)) {
    return NextResponse.json(birdCache.get(cacheKey))
  }

  try {
    const response = await fetch(`${BASE_URL}/${stationId}`)

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`)
    }

    const data = await response.json()

    birdCache.set(cacheKey, data)

    return NextResponse.json(data)
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch bird data' },
      { status: 500 },
    )
  }
}
