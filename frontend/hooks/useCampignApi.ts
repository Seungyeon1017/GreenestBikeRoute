import { useEffect, useState } from 'react'

interface BikeStatEntry {
  ZEIT: string
  Distanz: number
  Stunden: number
  Kcal: number
  Tracks: number
  date?: Date
}

interface BikeStatisticsResponse {
  stats: Omit<BikeStatEntry, 'date'>[]
}

type TrafficStatsResponse = {
  weekly_stats: WeeklyStat[]
}

type WeeklyStat = {
  week: string
  total_distance_m: number
  total_duration_s: number
  total_kcal: number
  trip_count: number
}

const formatDate = (date: Date): string => {
  const day = date.getDate().toString().padStart(2, '0')
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const year = date.getFullYear()
  return `${day}.${month}.${year}`
}

const transformToEntry = (label: string, raw: any): BikeStatEntry => {
  const date = new Date(label)
  return {
    ZEIT: formatDate(date),
    Distanz: raw.total_distance_m / 1000,
    Stunden: raw.total_duration_s / 3600,
    Kcal: Math.round(raw.total_kcal),
    Tracks: raw.trip_count,
    date,
  }
}

export function useBikeStatistics() {
  const [data, setData] = useState<BikeStatisticsResponse | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('/api/trafficstats', { cache: 'no-store' })

        if (!response.ok) {
          setData(null)
          return
        }

        const payload = (await response.json()) as TrafficStatsResponse
        const weeklyStats = payload.weekly_stats ?? []

        const entries: BikeStatEntry[] = [
          ...weeklyStats.map((week: WeeklyStat) =>
            transformToEntry(week.week, week),
          ),
        ]

        entries.sort(
          (a, b) => (b.date?.getTime() ?? 0) - (a.date?.getTime() ?? 0),
        )
        entries.reverse()

        let cumulativeDistance = 0
        let cumulativeTime = 0
        let cumulativeKcal = 0
        let cumulativeTracks = 0

        const cumulativeEntries = entries.map(entry => {
          cumulativeDistance += entry.Distanz
          cumulativeTime += entry.Stunden
          cumulativeKcal += entry.Kcal
          cumulativeTracks += entry.Tracks

          return {
            ...entry,
            Distanz: cumulativeDistance,
            Stunden: cumulativeTime,
            Kcal: cumulativeKcal,
            Tracks: cumulativeTracks,
          }
        })
        const stats = cumulativeEntries.map(({ date: _date, ...rest }) => rest)

        setData({ stats })
      } catch {
        setData(null)
      }
    }

    fetchData()
  }, [])

  return data
}
