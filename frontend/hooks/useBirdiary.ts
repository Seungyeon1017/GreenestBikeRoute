import { useEffect, useState } from 'react'

export interface BirdDetection {
  latinName: string
  germanName: string
  score: number
}

export interface BirdMovement {
  station_id: string
  mov_id: string
  start_date: string
  end_date: string
  weight: number
  detections: BirdDetection[]
  audio: string
  video: string
  createdAt: string
}

export interface BirdDayCount {
  sum: number
  birds: {
    latinName: string
    germanName: string
    amount: number
  }[]
}

export interface BirdStationData {
  station_id: string
  name: string
  location: {
    lat: number
    lng: number
  }
  count: Record<string, BirdDayCount>
  lastMovement: BirdMovement
  movements: BirdMovement[]
}

export default function useBirdiary(stationId: string) {
  const [data, setData] = useState<BirdStationData | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!stationId) {
      return
    }

    setIsLoading(true)
    fetch(`/api/birdiary?stationId=${stationId}`)
      .then(res => res.json())
      .then((stationData: BirdStationData) => {
        setData(stationData)
      })
      .catch(() => {
        // ignore fetch errors
      })
      .finally(() => {
        setIsLoading(false)
      })
  }, [stationId])

  return { data, isLoading }
}
