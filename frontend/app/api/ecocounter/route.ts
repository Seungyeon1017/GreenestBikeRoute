import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'
import { format, startOfYear, subDays } from 'date-fns'

const apiKey = process.env.ECOCOUNTER_API_KEY

const BASE_URL = 'https://api.eco-counter.com/api/v2/history/traffic/aggregated'

const ttl = 60 * 60 * 1000 // 1 hour

const trafficCache = new TTLCache<string, any>({ ttl })

export const GET = async (req: Request) => {
  if (!apiKey) {
    return NextResponse.json({ error: 'Missing API key' }, { status: 500 })
  }

  const { searchParams } = new URL(req.url)
  const siteId = searchParams.get('siteId')

  if (!siteId) {
    return NextResponse.json(
      { error: 'Missing siteId parameter' },
      { status: 400 },
    )
  }

  const cacheKey = `trafficData-${siteId}`

  if (trafficCache.has(cacheKey)) {
    return NextResponse.json(trafficCache.get(cacheKey))
  }

  try {
    const today = new Date()
    const endDate = format(subDays(new Date(), 0), 'yyyy-MM-dd')
    const startDate = format(subDays(new Date(), 7), 'yyyy-MM-dd')
    const yearStartDate = format(startOfYear(today), 'yyyy-MM-dd')

    const weekresponse = await fetch(
      `${BASE_URL}?siteId=${siteId}&startDate=${startDate}&endDate=${endDate}`,
      { headers: { 'X-API-KEY': apiKey } },
    )

    if (!weekresponse.ok) {
      throw new Error(`API request failed with status ${weekresponse.status}`)
    }
    const weekData = await weekresponse.json()
    const formattedWeekData = weekData['0'].data.map((entry: any) => ({
      counts: entry.traffic.counts,
      date: entry.timestamp,
    }))
    const yearResponse = await fetch(
      `${BASE_URL}?siteId=${siteId}&startDate=${yearStartDate}&endDate=${endDate}&granularity=P1Y`,
      { headers: { 'X-API-KEY': apiKey } },
    )
    if (!yearResponse.ok) {
      throw new Error(
        `Year API request failed with status ${yearResponse.status}`,
      )
    }
    const yearData = await yearResponse.json()
    const countsPerYear = yearData['0'].data.reduce(
      (sum: number, entry: any) => sum + entry.traffic.counts,
      0,
    )

    const responseData = [
      ...formattedWeekData,
      {
        countsPerYear,
        year: new Date().getFullYear(),
      },
    ]

    trafficCache.set(cacheKey, responseData)

    return NextResponse.json(responseData)
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : 'Failed to fetch data',
      },
      { status: 500 },
    )
  }
}
