import { NextResponse } from 'next/server'
import TTLCache from '@isaacs/ttlcache'
import { format, parse, subDays } from 'date-fns'
import { de } from 'date-fns/locale'

const CACHE_TTL = 60 * 60 * 1000 // 1 hour
const neosensCache = new TTLCache<string, any>({ ttl: CACHE_TTL })

interface DailyCount {
  counts: number
  date: Date
}

interface YearlyCount {
  countsPerYear: number
  year: number
}

interface ApiResponse {
  cuId: number
  dailyTotalTraffic: number
  yearlyTotalPedestrian: number
  yearlyTotalBike: number
  fullDataDaily: {
    labels: string[]
    datasets: {
      totalBikes: number[]
      totalPedestrians: number[]
    }
  }
}

function getYesterdayString(): string {
  return format(subDays(new Date(), 1), 'yyyy-MM-dd')
}

export const GET = async (req: Request) => {
  try {
    const { searchParams } = new URL(req.url)
    const cuId = searchParams.get('cuId')

    if (!cuId) {
      return NextResponse.json(
        { error: 'Missing cuId parameter' },
        { status: 400 },
      )
    }

    const cuIdNum = Number(cuId)
    if (isNaN(cuIdNum)) {
      return NextResponse.json(
        { error: 'Invalid cuId parameter' },
        { status: 400 },
      )
    }

    const cacheKey = `neosens-data-${cuId}`
    if (neosensCache.has(cacheKey)) {
      return NextResponse.json(neosensCache.get(cacheKey))
    }

    const cuIdsParam = encodeURIComponent(JSON.stringify([cuIdNum]))
    const apiUrl = `https://api.neocount.de/traffic-counts/sensor-data?cuIds=${cuIdsParam}`
    const response = await fetch(apiUrl)

    if (!response.ok) {
      throw new Error(`API request failed with status ${response.status}`)
    }

    const data: ApiResponse[] = await response.json()
    if (!data || !data.length) {
      return NextResponse.json([], { status: 200 })
    }

    const { fullDataDaily, yearlyTotalBike } = data[0]
    const { labels, datasets } = fullDataDaily
    const { totalBikes } = datasets

    const allDailyCounts: DailyCount[] = labels
      .map((label, index) => {
        const formattedDate = parse(label, 'd. MMMM yyyy', new Date(), {
          locale: de,
        })
        formattedDate.setHours(12, 0, 0, 0) // Set to noon to avoid timezone issues

        const count = totalBikes[index]

        if (!formattedDate || count === 0) {
          return null
        }
        return { date: formattedDate, counts: count }
      })
      .filter(Boolean) as DailyCount[]

    const yesterdayString = getYesterdayString()

    const yesterdayIndex = allDailyCounts.findIndex(
      d => format(d.date, 'yyyy-MM-dd') === yesterdayString,
    )

    const dailyCounts =
      yesterdayIndex >= 0
        ? allDailyCounts.slice(
            Math.max(0, yesterdayIndex - 6),
            yesterdayIndex + 1,
          )
        : allDailyCounts.slice(-7)

    const currentYear = dailyCounts.length
      ? new Date(dailyCounts[dailyCounts.length - 1].date).getFullYear()
      : new Date().getFullYear()

    const yearlyCount: YearlyCount = {
      countsPerYear: yearlyTotalBike,
      year: currentYear,
    }

    const responseData = [...dailyCounts, yearlyCount]
    neosensCache.set(cacheKey, responseData)

    return NextResponse.json(responseData)
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error ? error.message : 'Unexpected server error',
      },
      { status: 500 },
    )
  }
}
