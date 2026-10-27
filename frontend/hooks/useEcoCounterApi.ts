import { useEffect, useMemo, useState } from 'react'

type EcoCounterDailyData = {
  counts: number
  date: string
}

type EcoCounterYearlyData = {
  countsPerYear: number
  year: number
}

interface EcoCounterStationData {
  id: string
  name: string
  weeklyData: EcoCounterDailyData[]
  yearlyData: EcoCounterYearlyData[]
}

interface Station {
  id: string
  name: string
}

interface ProcessedStationData {
  id: string
  name: string
  weeklyCount: number
  yearlyCount: number
}

interface UseEcoCounterResult {
  loading: boolean
  data: ProcessedStationData[]
  min: number
  max: number
  stationCount: number
}

const ECO_COUNTER_STATIONS: Station[] = [
  { name: 'MZ-Kastel, Rheinufer', id: '300023897' },
  { name: 'Erbenheim / Kalkhofen', id: '300022664' },
]

const NEO_SENSE_STATIONS: Station[] = [
  { name: 'Stresemann-Ring', id: '1836' },
  { name: 'Bertramstraße', id: '1837' },
]

const normalizeDate = (date: Date) =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()

const fetchBicycleData = async (
  stationId: string,
): Promise<EcoCounterStationData> => {
  const response = await fetch(`/api/ecocounter?siteId=${stationId}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch data for station ${stationId}`)
  }
  const data = await response.json()

  return {
    id: stationId,
    name: ECO_COUNTER_STATIONS.find(s => s.id === stationId)?.name || stationId,
    weeklyData: data.filter((d: any) => 'counts' in d),
    yearlyData: data.filter((d: any) => 'countsPerYear' in d),
  }
}

const fetchNeosensData = async (
  cuIdsParam: string,
): Promise<EcoCounterStationData> => {
  const response = await fetch(`/api/neosens?cuId=${cuIdsParam}`)
  if (!response.ok) {
    throw new Error('Failed to fetch Neosens data')
  }
  const data = await response.json()
  return {
    id: cuIdsParam,
    name: NEO_SENSE_STATIONS.find(s => s.id === cuIdsParam)?.name || cuIdsParam,
    weeklyData: data.filter((d: any) => 'counts' in d),
    yearlyData: data.filter((d: any) => 'countsPerYear' in d),
  }
}

const processStationData = (
  stations: EcoCounterStationData[],
  normalizedDate: number,
  currentYear: number,
): ProcessedStationData[] => {
  return stations.map(station => {
    const weeklyCount =
      station.weeklyData.find(
        d => normalizeDate(new Date(d.date)) === normalizedDate,
      )?.counts || 0

    const yearlyCount =
      station.yearlyData.find(y => y.year === currentYear)?.countsPerYear || 0

    return {
      id: station.id,
      name: station.name,
      weeklyCount,
      yearlyCount,
    }
  })
}

export function useEcoCounter(timestamp: Date): UseEcoCounterResult {
  const [loading, setLoading] = useState(true)
  const [ecoCounterData, setEcoCounterData] = useState<EcoCounterStationData[]>(
    [],
  )
  const [neosensData, setNeosensData] = useState<EcoCounterStationData[]>([])

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [ecoData, neoData] = await Promise.all([
          Promise.all(
            ECO_COUNTER_STATIONS.map(station => fetchBicycleData(station.id)),
          ),
          Promise.all(
            NEO_SENSE_STATIONS.map(station => fetchNeosensData(station.id)),
          ),
        ])
        setEcoCounterData(ecoData)
        setNeosensData(neoData)
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error fetching data:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const { data, min, max } = useMemo(() => {
    if (loading) {
      return {
        data: [],
        min: 0,
        max: 0,
      }
    }

    const normalizedDate = normalizeDate(timestamp)
    const currentYear = new Date().getFullYear()
    const ecoStations = processStationData(
      ecoCounterData,
      normalizedDate,
      currentYear,
    )
    const neoSensStations = processStationData(
      neosensData,
      normalizedDate,
      currentYear,
    )

    const combinedData = [...ecoStations, ...neoSensStations]

    const weeklyCounts = combinedData.map(d => d.weeklyCount || 0)
    const min = weeklyCounts.length ? Math.min(...weeklyCounts) : 0
    const max = weeklyCounts.length ? Math.max(...weeklyCounts) : 0

    return {
      data: combinedData,
      min,
      max,
    }
  }, [loading, ecoCounterData, neosensData, timestamp])

  return {
    loading,
    data,
    min,
    max,
    stationCount: ECO_COUNTER_STATIONS.length + NEO_SENSE_STATIONS.length,
  }
}
