import { useEffect, useState } from 'react'

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

export type TrafficStatsData = {
  latest_stats: LatestStats
  weekly_stats: WeeklyStatEntry[]
}

export default function useTrafficStats() {
  const [data, setData] = useState<TrafficStatsData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/trafficstats', { cache: 'no-store' })

        if (!response.ok) {
          throw new Error('Failed to fetch traffic statistics')
        }

        const json = (await response.json()) as TrafficStatsData
        setData(json)
      } catch {
        setError('Failed to load traffic statistics')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  return { data, isLoading, error }
}
