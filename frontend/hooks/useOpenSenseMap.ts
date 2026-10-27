import { useEffect, useState } from 'react'

export interface SenseBoxSensor {
  _id: string
  icon: string
  title: string
  unit: string
  lastMeasurement?: {
    value: string
    createdAt: string
  }
}

export interface SenseBox {
  _id: string
  name: string
  grouptag: string[]
  model: string
  exposure: string
  currentLocation: {
    type: string
    coordinates: [number, number] // [lng, lat]
    timestamp: string
  }
  sensors: SenseBoxSensor[]
  updatedAt: string
  createdAt: string
}

export default function useOpenSenseMap(grouptag: string) {
  const [data, setData] = useState<SenseBox[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!grouptag) {
      return
    }

    const fetchData = async () => {
      setIsLoading(true)
      try {
        const response = await fetch(
          `/api/opensensemap?grouptag=${encodeURIComponent(grouptag)}`,
        )
        if (!response.ok) {
          throw new Error('Failed to fetch')
        }
        const json = await response.json()
        setData(json)
      } catch {
        // silently fail
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [grouptag])

  return { data, isLoading }
}
