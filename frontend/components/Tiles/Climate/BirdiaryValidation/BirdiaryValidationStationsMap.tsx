'use client'

import { type BirdMovement, type BirdStationData } from '@/hooks/useBirdiary'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface BirdiaryValidationStationsMapProps {
  stationIds: string[]
}

interface StationWithNewestVideo {
  stationId: string
  name: string
  location: {
    lat: number
    lng: number
  }
  newestVideoUrl?: string
}

function getMovementTimestamp(movement: BirdMovement): number {
  const candidateDate = movement.createdAt || movement.start_date
  const normalized = candidateDate?.includes(' ')
    ? candidateDate.replace(' ', 'T')
    : candidateDate
  const timestamp = normalized ? new Date(normalized).getTime() : NaN
  return Number.isFinite(timestamp) ? timestamp : 0
}

function pickNewestVideo(data: BirdStationData): {
  url?: string
  date?: string
} {
  const candidates = [data.lastMovement, ...(data.movements ?? [])]
    .filter((movement): movement is BirdMovement => !!movement && !!movement.video)

  if (candidates.length === 0) {
    return {}
  }

  const newest = candidates.reduce((latest, current) => {
    return getMovementTimestamp(current) > getMovementTimestamp(latest)
      ? current
      : latest
  })

  return {
    url: newest.video,
    date: newest.start_date || newest.createdAt,
  }
}

function BirdiaryValidationMap({
  stations,
  selectedStationId,
  onSelectStation,
}: {
  stations: StationWithNewestVideo[]
  selectedStationId: string | null
  onSelectStation: (_s: StationWithNewestVideo) => void
}) {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const markersRef = useRef<{ stationId: string; el: HTMLButtonElement; marker: maplibregl.Marker }[]>([])

  useEffect(() => {
    if (!mapContainer.current || stations.length === 0) {
      return
    }

    if (mapRef.current) {
      return
    }

    const firstStation = stations[0]
    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
      center: [firstStation.location.lng, firstStation.location.lat],
      zoom: 12,
      attributionControl: false,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [stations])

  // Add/rebuild markers when stations change
  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }

    for (const { marker } of markersRef.current) {
      marker.remove()
    }
    markersRef.current = []

    const addMarkers = () => {
      for (const station of stations) {
        const isActive = station.stationId === selectedStationId
        const markerEl = document.createElement('button')
        markerEl.type = 'button'
        markerEl.setAttribute('aria-label', station.name)
        markerEl.style.width = '18px'
        markerEl.style.height = '18px'
        markerEl.style.borderRadius = '50%'
        markerEl.style.backgroundColor = !station.newestVideoUrl
          ? '#9ca3af'
          : isActive
            ? '#f97316'
            : '#0ea5e9'
        markerEl.style.border = isActive ? '2.5px solid #f97316' : '2.5px solid white'
        markerEl.style.boxShadow = isActive
          ? '0 0 0 3px rgba(249,115,22,0.3)'
          : '0 1px 4px rgba(0,0,0,0.3)'
        markerEl.style.cursor = station.newestVideoUrl ? 'pointer' : 'default'
        markerEl.style.transition = 'background-color 0.2s, box-shadow 0.2s'

        if (station.newestVideoUrl) {
          markerEl.addEventListener('click', () => {
            onSelectStation(station)
          })
        }

        const marker = new maplibregl.Marker({ element: markerEl })
          .setLngLat([station.location.lng, station.location.lat])
          .addTo(map)

        markersRef.current.push({ stationId: station.stationId, el: markerEl, marker })
      }

      if (stations.length > 1) {
        const bounds = new maplibregl.LngLatBounds()
        for (const station of stations) {
          bounds.extend([station.location.lng, station.location.lat])
        }
        map.fitBounds(bounds, { padding: 50 })
      }
    }

    if (map.loaded()) {
      addMarkers()
      return
    }

    map.once('load', addMarkers)
  }, [stations, onSelectStation])

  // Update marker colors when selection changes without re-adding all markers
  useEffect(() => {
    for (const { stationId, el } of markersRef.current) {
      const station = stations.find(s => s.stationId === stationId)
      const isActive = stationId === selectedStationId
      if (!station?.newestVideoUrl) { continue }
      el.style.backgroundColor = isActive ? '#f97316' : '#0ea5e9'
      el.style.border = isActive ? '2.5px solid #f97316' : '2.5px solid white'
      el.style.boxShadow = isActive
        ? '0 0 0 3px rgba(249,115,22,0.3)'
        : '0 1px 4px rgba(0,0,0,0.3)'
    }
  }, [selectedStationId, stations])

  return (
    <div
      className="min-h-[380px] w-full overflow-hidden rounded-lg"
      ref={mapContainer}
    />
  )
}

export default function BirdiaryValidationStationsMap({
  stationIds,
}: BirdiaryValidationStationsMapProps) {
  const { t } = useTranslation()
  const [isLoading, setIsLoading] = useState(true)
  const [stationsData, setStationsData] = useState<BirdStationData[]>([])
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const loadStations = async () => {
      setIsLoading(true)
      try {
        const responses = await Promise.all(
          stationIds.map(async stationId => {
            const response = await fetch(`/api/birdiary?stationId=${stationId}`)
            if (!response.ok) {
              return null
            }
            return (await response.json()) as BirdStationData
          }),
        )

        if (!cancelled) {
          setStationsData(
            responses.filter(
              (station): station is BirdStationData => !!station?.location,
            ),
          )
        }
      } catch {
        if (!cancelled) {
          setStationsData([])
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    loadStations()

    return () => {
      cancelled = true
    }
  }, [stationIds])

  const stations = useMemo<StationWithNewestVideo[]>(() => {
    const results: StationWithNewestVideo[] = []
    stationsData.forEach((station, index) => {
      if (!station?.location) { return }
      const newestVideo = pickNewestVideo(station)
      results.push({
        stationId: station.station_id || stationIds[index],
        name: station.name || station.station_id,
        location: station.location,
        newestVideoUrl: newestVideo.url,
      })
    })
    return results
  }, [stationIds, stationsData])

  useEffect(() => {
    if (!selectedStationId) {
      const firstWithVideo = stations.find(station => !!station.newestVideoUrl)
      if (firstWithVideo) {
        setSelectedStationId(firstWithVideo.stationId)
      }
      return
    }

    const selectedStillExists = stations.some(
      station => station.stationId === selectedStationId && !!station.newestVideoUrl,
    )

    if (!selectedStillExists) {
      const fallback = stations.find(station => !!station.newestVideoUrl)
      setSelectedStationId(fallback?.stationId ?? null)
    }
  }, [stations, selectedStationId])

  const selectedStation = stations.find(
    station => station.stationId === selectedStationId,
  )

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-climate border-t-transparent" />
      </div>
    )
  }

  if (stations.length === 0) {
    return (
      <p className="text-sm text-gray-500">{t('birdiaryValidation.noStations')}</p>
    )
  }

  return (
    <div className="relative">
      <BirdiaryValidationMap
        onSelectStation={station => {
          if (station.newestVideoUrl) {
            setSelectedStationId(station.stationId)
          }
        }}
        selectedStationId={selectedStationId}
        stations={stations}
      />

      {selectedStation?.newestVideoUrl && (
        <div className="absolute bottom-3 right-3 z-10 w-56 overflow-hidden rounded-lg bg-black shadow-lg ring-1 ring-black/20">
          <button
            aria-label="Close video"
            className="absolute right-1 top-1 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white hover:bg-black/80"
            onClick={() => setSelectedStationId(null)}
            type="button"
          >
            <span className="text-xs leading-none">✕</span>
          </button>
          <video
            autoPlay
            className="w-full"
            controls
            key={selectedStation.stationId}
            playsInline
            src={selectedStation.newestVideoUrl}
          >
            <track kind="captions" />
          </video>
        </div>
      )}
    </div>
  )
}