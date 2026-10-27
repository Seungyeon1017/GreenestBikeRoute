import { useEffect, useState } from 'react'

export interface Root {
  type: string
  features: Feature[]
  numberMatched: number
  numberReturned: number
  links: Link[]
  timeStamp: string
}

export interface Feature {
  type: string
  properties: Properties
  id: number
  geometry: Geometry
}

export interface Properties {
  'Average Distance to Road': number
  access: any
  'Number of Points': number
  name?: string
  service: any
  osmid: string
  highway: string
  tunnel: any
  'Average Overtaking Distance': number
  reversed: string
  area: any
  'Average Overtaking Manoeuvre': number
  length: number
  junction: any
  est_width: any
  'Average Normalized Overtaking Distance': number
  lanes?: string
  bridge: any
  maxspeed?: string
  width?: string
  oneway: boolean
  ref: any
}

export interface Geometry {
  type: string
  coordinates: number[][]
}

export interface Link {
  type: string
  rel: string
  title: string
  href: string
}
interface OvertakingData {
  data: Root | null

  min: number
  max: number
}

function useOvertakingManoeuvres(): OvertakingData {
  const [result, setResult] = useState<OvertakingData>({
    data: null,
    min: 0,
    max: 10,
  })

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          'https://api.atrai.bike/collections/overtaking_distance_heilbronn/items?f=json&limit=100000',
        )
        const jsonData: Root = await response.json()

        let minPoints = Infinity
        let maxPoints = -Infinity

        jsonData.features.forEach(feature => {
          const points = feature.properties['Number of Points']
          minPoints = Math.min(minPoints, points)
          maxPoints = Math.max(maxPoints, points)
        })

        setResult({
          data: jsonData,

          min: minPoints,
          max: maxPoints,
        })
      } catch (error) {
        console.error('Error fetching data:', error)
        setResult({
          data: null,
          min: 0,
          max: 10,
        })
      }
    }

    fetchData()
  }, [])

  return result
}

export default useOvertakingManoeuvres
