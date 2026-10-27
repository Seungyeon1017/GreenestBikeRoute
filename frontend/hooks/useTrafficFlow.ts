import { useEffect, useState } from 'react'

export type TrafficFlowProperties = {
  points_in_segment?: number
  road_segment?: number
  name?: string | null
  oneway?: boolean | null
  cycleway?: string | null
  osmid?: string
  avg_traffic_flow?: number
  junction?: string | null
}

export type TrafficFlowFeature = {
  type: 'Feature'
  id?: number | string
  properties: TrafficFlowProperties
  geometry: {
    type: 'LineString'
    coordinates: [number, number][]
  }
}

export type TrafficFlowFeatureCollection = {
  type: 'FeatureCollection'
  features: TrafficFlowFeature[]
}

export default function useTrafficFlow() {
  const [data, setData] = useState<TrafficFlowFeatureCollection | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)
      setError(null)

      try {
        const response = await fetch('/api/trafficflow')

        if (!response.ok) {
          throw new Error('Failed to fetch traffic flow data')
        }

        const json = (await response.json()) as TrafficFlowFeatureCollection
        setData(json)
      } catch {
        setError('Failed to load traffic flow data')
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  return { data, isLoading, error }
}
