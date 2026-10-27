'use client'

import React, { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import Switch from '@/components/Inputs/Switch'
import '@maplibre/maplibre-gl-compare/dist/maplibre-gl-compare.css'
// @ts-ignore
import MaplibreCompare from '@maplibre/maplibre-gl-compare'
import DistanceBar from './DistanceBar'
import useDevice from '@/hooks/useDevice'
import useOvertakingManoeuvres from '@/hooks/useOvertakingManeuver'

interface Link {
  type?: string
  rel: string
  title: string
  href: string
}

interface OvertakingFeatureProperties {
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

interface LineString {
  type: 'LineString'
  coordinates: number[][]
}

interface OvertakingFeature {
  type: 'Feature'
  properties: OvertakingFeatureProperties
  id: number
  geometry: LineString
}

interface OvertakingFeatureCollection {
  type: 'FeatureCollection'
  numberMatched: number
  numberReturned: number
  links: Link[]
  timeStamp: string
  features: OvertakingFeature[]
}

function MapComparison() {
  const beforeMapContainer = useRef<HTMLDivElement>(null)
  const afterMapContainer = useRef<HTMLDivElement>(null)
  const comparisonContainer = useRef<HTMLDivElement>(null)
  const compareInstance = useRef<MaplibreCompare | null>(null)
  const afterMapRef = useRef<maplibregl.Map | null>(null)
  const { data: GeoData, min, max } = useOvertakingManoeuvres()
  const geoJsonData = GeoData as OvertakingFeatureCollection
  const [legendUrl, setLegendUrl] = useState<string>(
    'https://www.wms.nrw.de/wms/unfallatlas?request=GetLegendGraphic&version=1.3.0&format=image/png&layer=Beteiligung_Fahrrad_250',
  )
  const [useunfallOrte, setUseunfallOrte] = useState(false)
  const device = useDevice()

  const toggleLayer = (checked: boolean) => {
    setUseunfallOrte(checked)
    setLegendUrl(
      checked
        ? 'https://www.wms.nrw.de/wms/unfallatlas?request=GetLegendGraphic&version=1.3.0&format=image/png&layer=Unfallorte'
        : 'https://www.wms.nrw.de/wms/unfallatlas?request=GetLegendGraphic&version=1.3.0&format=image/png&layer=Beteiligung_Fahrrad_250',
    )

    if (afterMapRef.current) {
      const map = afterMapRef.current
      if (map.getLayer('wms-layer-right')) {
        map.removeLayer('wms-layer-right')
      }
      if (map.getSource('wms-right')) {
        map.removeSource('wms-right')
      }

      map.addSource('wms-right', {
        type: 'raster',
        tiles: [
          `https://www.wms.nrw.de/wms/unfallatlas?service=WMS&request=GetMap&version=1.3.0&layers=${checked ? 'Unfallorte' : 'Beteiligung_Fahrrad_250'}&styles=&format=image/png&transparent=true&width=256&height=256&crs=EPSG:3857&bbox={bbox-epsg-3857}`,
        ],
        tileSize: 256,
      })

      map.addLayer({
        id: 'wms-layer-right',
        type: 'raster',
        source: 'wms-right',
        paint: {},
      })
    }
  }

  useEffect(() => {
    if (
      !beforeMapContainer.current ||
      !afterMapContainer.current ||
      !comparisonContainer.current
    ) {
      return
    }

    const beforeMap = new maplibregl.Map({
      container: beforeMapContainer.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [9.218, 49.1399], // Heilbronn coordinates
      zoom: 12,
      attributionControl: false,
      maxBounds: [
        [8.9, 48.9],
        [9.5, 49.4],
      ],
    })

    const afterMap = new maplibregl.Map({
      container: afterMapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto-light': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
              'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
            ],
            attribution: '', // Empty attribution
          },
        },
        layers: [
          {
            id: 'carto-light-layer',
            type: 'raster',
            source: 'carto-light',
          },
        ],
      },
      zoom: 12,
      attributionControl: false,
      center: [9.218, 49.1399], // Heilbronn coordinates
      maxBounds: [
        [8.9, 48.9],
        [9.5, 49.4],
      ],
    })

    afterMapRef.current = afterMap

    // Add WMS layers when maps load
    beforeMap.on('load', () => {
      beforeMap.addSource('overtaking-data', {
        type: 'geojson',
        data: geoJsonData,
      })

      // Add the layer with style based on properties
      beforeMap.addLayer({
        id: 'overtaking-lines',
        type: 'line',
        source: 'overtaking-data',
        paint: {
          'line-color': [
            'case',
            ['has', 'Average Normalized Overtaking Distance'],
            [
              'interpolate',
              ['linear'],
              ['get', 'Average Normalized Overtaking Distance'],
              0,
              '#00ff00',
              0.5,
              '#ffff00',
              1,
              '#ff0000',
            ],
            '#ccc',
          ],
          'line-opacity': [
            'case',
            ['has', 'Number of Points'],
            [
              'interpolate',
              ['linear'],
              ['get', 'Number of Points'],
              min,
              0.6,
              max / 2,
              0.8,
              max,
              1,
            ],
            0.5,
          ],
          'line-width': 3,
        },
      })
    })

    afterMap.on('load', () => {
      afterMap.addControl(
        new maplibregl.AttributionControl({
          customAttribution:
            '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a> | <a href="https://unfallatlas.statistikportal.de/" target="_blank" rel="noopener noreferrer">Map Data © Unfallatlas</a> | <a href="https://www.govdata.de/dl-de/by-2-0" target="_blank" rel="noopener noreferrer">dl-de/by-2-0</a>',
        }),
      )
      afterMap.addSource('wms-right', {
        type: 'raster',
        tiles: [
          'https://www.wms.nrw.de/wms/unfallatlas?service=WMS&request=GetMap&version=1.3.0&layers=Beteiligung_Fahrrad_250&styles=&format=image/png&transparent=true&width=256&height=256&crs=EPSG:3857&bbox={bbox-epsg-3857}&time=2024-01-01T00:00:00Z',
        ],
        tileSize: 256,
      })
      afterMap.addLayer({
        id: 'wms-layer-right',
        type: 'raster',
        source: 'wms-right',
        paint: {},
      })
      compareInstance.current = new MaplibreCompare(
        beforeMap,
        afterMap,
        comparisonContainer.current,
        {
          mousemove: false,
          orientation: device === 'mobile' ? 'horizontal' : 'vertical',
        },
      )
    })

    return () => {
      // Cleanup
      compareInstance.current?.remove()
      beforeMap.remove()
      afterMap.remove()
      afterMapRef.current = null
    }
  }, [device, geoJsonData, min, max])

  return (
    <div
      className="relative rounded-md"
      ref={comparisonContainer}
      style={{
        width: '100%',
        height: '500px',
        overflow: 'hidden',
      }}
    >
      <div
        ref={beforeMapContainer}
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
        }}
      >
        <div
          className={`${device === 'mobile' ? 'top-2' : 'bottom-2'}`}
          style={{
            position: 'absolute',
            width: '100%',
            padding: '20px',

            zIndex: 10,
          }}
        >
          <DistanceBar />
        </div>
      </div>
      <div
        ref={afterMapContainer}
        style={{
          position: 'absolute',
          width: '100%',
          height: '100%',
        }}
      >
        <div className="pointer-events-none absolute inset-0">
          <div
            className={`pointer-events-auto absolute ${device === 'mobile' ? 'bottom-0 left-0' : 'right-0 top-0'} z-20 rounded-md bg-white px-3 py-2`}
          >
            <Switch
              defaultChecked={useunfallOrte}
              label="Unfallorte"
              onCheckedChange={toggleLayer}
              variant="mobility"
            />
          </div>
          <div className="pointer-events-auto absolute bottom-3 right-3 z-10 flex flex-col items-end space-y-2">
            <div className="mb-3 rounded bg-white bg-opacity-80 p-1 shadow-md">
              <img
                alt="Map Legend"
                className="h-auto max-w-[150px]"
                src={legendUrl}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MapComparison
