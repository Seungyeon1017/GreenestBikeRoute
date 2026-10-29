'use client'

import type { FeatureCollection, LineString } from 'geojson'
import maplibregl from 'maplibre-gl'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import BaseMap from '@/components/Greenest/Map'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import useCommunityRouteFromUrl from '@/hooks/useCommunityRouteFromUrl'
import { closureNear, useReports } from '@/hooks/useReports'
import useSavedRouteFromUrl from '@/hooks/useSavedRouteFromUrl'
import { useSharedVehicles, useSharingTrip } from '@/hooks/useSharing'
import { GRADE_COLOR } from '@/lib/hillColors'
import { readTripLink } from '@/lib/shareLink'
import {
  DEFAULT_ROUTE_OPTIONS,
  fetchGeofencing,
  fetchReportFootway,
  fetchReportSegment,
  fetchRouteComparison,
  fetchRouteDay,
  fetchRouteGrade,
} from '@/services/greenestApi'
import { fromSavedOptions } from '@/services/usersApi'
import type { CommunityRoute } from '@/types/users'
import type {
  ClosureCollection,
  ClosureStatus,
  DayRoutes,
  FootwayFeature,
  GeofencingCollection,
  GradeCollection,
  LngLat,
  MappingCollection,
  ReportKind,
  ReportPick,
  RouteFlag,
  RouteKind,
  RouteOptions,
  RouteComparison as RouteResult,
  RouteSegment,
  SharingTrip,
  SharingVehicleChoice,
  StreetSegmentFeature,
  VehicleCollection,
  ZoneCollection,
} from '@/types/greenest'
import ContributeRouteCard from './ContributeRouteCard'
import DaySlider, { dayStops, stopAt } from './DaySlider'
import GradeCard from './GradeCard'
import LeisureRouteCard from './LeisureRouteCard'
import { drawLeisure, lineBounds } from './leisureLayers'
import {
  CLICKABLE_REPORT_LAYERS,
  drawReportPicks,
  drawReports,
  reportPopup,
} from './reportLayers'
import ReportProblem from './ReportProblem'
import ReportsCard, { closureText } from './ReportsCard'
import RouteComparisonCard, { ROUTE_COLORS } from './RouteComparison'
import SaveRouteButton from './SaveRouteButton'
import {
  drawSegments,
  flagBounds,
  highlightFlag,
  markSegment,
  SEGMENT_HIT_LAYER,
  segmentAt,
  segmentPopup,
} from './routeSegments'
import type { SegmentLabels } from './routeSegments'
import SharingCard, {
  localPrice,
  priceFor,
  safeRentUrl,
  VEHICLE_COLORS,
  WALK_COLOR,
} from './SharingCard'
import TripForm from './TripForm'
import {
  attachPinPopup,
  CLICKABLE_SHARING_LAYERS,
  drawSharing,
  drawTrip,
  fadeRoutes,
  pinPopup,
  sharingPopup,
  tripPin,
} from './sharingLayers'
import type { PinInfo } from './sharingLayers'

const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] }

/** Rounded corners and ends, so a route's many small bends don't look jagged. */
const ROUND_LINE: maplibregl.LineLayerSpecification['layout'] = {
  'line-cap': 'round',
  'line-join': 'round',
}

/** How close (px) a click must be to a shared vehicle or zone to open its popup. */
const CLICK_TOLERANCE_PX = 10

/** Creates the two route layers the first time, then puts the current result into them. */
function drawRoutes(map: maplibregl.Map, result: RouteResult | null) {
  if (!map.getSource('shortest')) {
    map.addSource('shortest', { type: 'geojson', data: EMPTY })
    map.addSource('greenest', { type: 'geojson', data: EMPTY })
    map.addLayer({
      id: 'shortest',
      type: 'line',
      source: 'shortest',
      // Round corners only: round ends would turn the short dashes into dots.
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': ROUTE_COLORS.shortest,
        'line-width': 5,
        'line-dasharray': [2, 2],
      },
    })
    map.addLayer({
      id: 'greenest',
      type: 'line',
      source: 'greenest',
      layout: ROUND_LINE,
      paint: { 'line-color': ROUTE_COLORS.greenest, 'line-width': 6 },
    })
  }
  map
    .getSource<maplibregl.GeoJSONSource>('shortest')
    ?.setData(result?.shortest ?? EMPTY)
  map
    .getSource<maplibregl.GeoJSONSource>('greenest')
    ?.setData(result?.route ?? EMPTY)
}

/** Draws the route's steepness pieces on top of the green line, or clears them. */
function drawGrade(map: maplibregl.Map, grade: GradeCollection | null) {
  if (!map.getSource('grade')) {
    map.addSource('grade', { type: 'geojson', data: EMPTY })
    // White edge so the pale flat and yellow pieces stand out from the map.
    map.addLayer({
      id: 'grade-casing',
      type: 'line',
      source: 'grade',
      layout: ROUND_LINE,
      paint: { 'line-color': '#ffffff', 'line-width': 9 },
    })
    map.addLayer({
      id: 'grade',
      type: 'line',
      source: 'grade',
      layout: ROUND_LINE,
      // Coloured from the exact grade (not the backend's five classes): uphill warm, downhill cool.
      paint: { 'line-color': GRADE_COLOR, 'line-width': 6 },
    })
  }
  map.getSource<maplibregl.GeoJSONSource>('grade')?.setData(grade ?? EMPTY)
}

/** Where riders can be routed (download_data.py, HEILBRONN_BBOX): west, south, east, north. */
const HEILBRONN_BBOX = [9.038, 49.083, 9.312, 49.22]

/** A fresh enough GPS fix: a minute old is still where the rider stands. */
const LOCATE_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 15000,
  maximumAge: 60000,
}

/** A clicked point as "lat, lng", the text shown in the search field. */
function formatPoint([lng, lat]: LngLat): string {
  return `${lat.toFixed(5)}, ${lng.toFixed(5)}`
}

/**
 * A draggable start or destination pin. MapLibre keeps the map still while a
 * pin is dragged; `onMove` gets the point where it was dropped. A plain click
 * on the pin doesn't reach the map, so it doesn't set the other point there.
 */
function endpointPin(
  map: maplibregl.Map,
  at: LngLat,
  color: string,
  label: string,
  onMove: (_point: LngLat) => void,
): maplibregl.Marker {
  const marker = new maplibregl.Marker({ color, draggable: true })
    .setLngLat(at)
    .addTo(map)
  const pin = marker.getElement()
  pin.style.cursor = 'grab'
  const tag = document.createElement('span')
  tag.textContent = label
  Object.assign(tag.style, {
    position: 'absolute',
    left: '50%',
    bottom: '100%',
    transform: 'translateX(-50%)',
    marginBottom: '2px',
    padding: '1px 6px',
    borderRadius: '9px',
    background: color,
    color: '#fff',
    font: '600 11px/16px system-ui, sans-serif',
    whiteSpace: 'nowrap',
    pointerEvents: 'none',
  })
  pin.appendChild(tag)
  pin.addEventListener('click', e => e.stopPropagation())
  marker.on('dragend', () => {
    const { lng, lat } = marker.getLngLat()
    onMove([lng, lat])
  })
  return marker
}

export default function PlanTripView() {
  const { t, i18n } = useTranslation()

  // 1. STATE: values that make the page redraw when they change.
  const [start, setStart] = useState<LngLat | null>(null)
  const [end, setEnd] = useState<LngLat | null>(null)
  // Text in the Start and Destination search fields.
  const [startLabel, setStartLabel] = useState('')
  const [endLabel, setEndLabel] = useState('')
  const [options, setOptions] = useState<RouteOptions>(DEFAULT_ROUTE_OPTIONS)
  const [result, setResult] = useState<RouteResult | null>(null)
  // True once the map has loaded, so a saved route opened from the Profile gets its pins.
  const [mapReady, setMapReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // "Use my location": waiting for the browser, and why it didn't work.
  const [locating, setLocating] = useState(false)
  const [locateError, setLocateError] = useState<string | null>(null)

  // Through the day: one /route/day request, then each time of day is only a redraw.
  const [dayMode, setDayMode] = useState(false)
  const [day, setDay] = useState<DayRoutes | null>(null)
  // The stop the rider picked ("12:00", "night"); kept when the settings change.
  const [dayKey, setDayKey] = useState<string | null>(null)
  const stops = useMemo(() => (day ? dayStops(day) : []), [day])
  const picked = stops.findIndex(s => s.key === dayKey)
  // Until one is picked: the time of day of the departure, else now.
  const stopIndex =
    picked >= 0
      ? picked
      : stopAt(
          stops,
          options.departTime.slice(11, 16) ||
            new Date().toTimeString().slice(0, 5),
        )
  const stop = dayMode ? stops[stopIndex] : undefined
  const pickStop = useCallback(
    (i: number) => setDayKey(stops[i]?.key ?? null),
    [stops],
  )
  // What the map and the comparison show: the chosen time of day, or the single departure.
  const shown = dayMode ? (stop?.period ?? null) : result
  // The hills and the rental trip follow the chosen time of day.
  const tripOptions = useMemo(
    () =>
      stop && day
        ? { ...options, departTime: `${day.date}T${stop.departAt}` }
        : options,
    [options, stop, day],
  )

  // Hills: only requested while "Show hills" is ticked.
  const [showHills, setShowHills] = useState(false)
  const [grade, setGrade] = useState<GradeCollection | null>(null)
  const [gradeError, setGradeError] = useState<string | null>(null)

  // Shared vehicles: on the map, and a trip with a rented one. Nothing loads while unticked.
  const [showSharing, setShowSharing] = useState(false)
  const [sharingVehicle, setSharingVehicle] =
    useState<SharingVehicleChoice>('bike')
  const [tripOn, setTripOn] = useState(false)
  const [tripVehicle, setTripVehicle] = useState<SharingVehicleChoice>('all')
  const [fences, setFences] = useState<GeofencingCollection | null>(null)
  const sharing = useSharedVehicles(showSharing, sharingVehicle, start)
  const sharingTrip = useSharingTrip(
    tripOn,
    tripVehicle,
    start,
    end,
    tripOptions,
  )

  // Riders' reports: closures and mapping mistakes.
  const reports = useReports()
  const [showReports, setShowReports] = useState(true)
  // What "Report a problem" reports at the next map click; null: a click plans the route.
  const [reportKind, setReportKind] = useState<ReportKind | null>(null)
  // Another map mistake: where the rider clicked, until the report is sent or cancelled.
  const [draft, setDraft] = useState<LngLat | null>(null)
  // A closed street or a footway: the segments or ways picked on the map.
  const [picks, setPicks] = useState<ReportPick[]>([])
  // Street or footway lookups under clicks still on their way.
  const [pending, setPending] = useState(0)
  const [pickError, setPickError] = useState<string | null>(null)
  const [reportStatus, setReportStatus] = useState<string | null>(null)
  // A closure near the trip's start or end to ask about: riders there know if it is still closed.
  const nearClosure = useMemo(
    () =>
      start && end && showReports
        ? closureNear(reports.closures, [start, end])
        : null,
    // `skipped`: a "don't know" puts the question aside (kept in localStorage).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [reports.closures, reports.skipped, start, end, showReports],
  )

  // 2. REFS: values kept between redraws that don't trigger a redraw themselves.
  const mapRef = useRef<maplibregl.Map | null>(null)
  const resultRef = useRef<RouteResult | null>(null)
  resultRef.current = shown
  const gradeRef = useRef<GradeCollection | null>(null)
  gradeRef.current = grade
  // The map's style can reload (fallback style), so keep what's needed to redraw.
  const sharingRef = useRef<{
    vehicles: VehicleCollection | null
    zones: ZoneCollection | null
  }>({ vehicles: null, zones: null })
  sharingRef.current = { vehicles: sharing.vehicles, zones: sharing.zones }
  const tripRef = useRef<SharingTrip | null>(null)
  tripRef.current = sharingTrip.trip
  const plainTripRef = useRef<SharingTrip | null>(null)
  plainTripRef.current = sharingTrip.plainTrip
  const fencesRef = useRef<GeofencingCollection | null>(null)
  fencesRef.current = fences
  const reportsRef = useRef<{
    closures: ClosureCollection | null
    mapping: MappingCollection | null
    show: boolean
  }>({ closures: null, mapping: null, show: true })
  reportsRef.current = {
    closures: reports.closures,
    mapping: reports.mapping,
    show: showReports,
  }
  const picksRef = useRef<ReportPick[]>([])
  picksRef.current = picks
  const reportKindRef = useRef<ReportKind | null>(null)
  reportKindRef.current = reportKind
  const popupRef = useRef<maplibregl.Popup | null>(null)
  // The stretch popup: follows the mouse while hovering a route line, stays put once clicked or tapped.
  const segmentPopupRef = useRef<{
    popup: maplibregl.Popup
    pinned: boolean
  } | null>(null)
  const segmentEventsRef = useRef(false)

  // "Why this route?" row whose stretches are drawn: the hovered one, else the clicked one.
  const [previewFlag, setPreviewFlag] = useState<RouteFlag | null>(null)
  const [pinnedFlag, setPinnedFlag] = useState<RouteFlag | null>(null)
  const shownFlag = previewFlag ?? pinnedFlag

  // A riders' leisure route on the map (?route=<id>, or just published), and a GPX upload not yet published.
  const [leisure, setLeisure] = useState<CommunityRoute | null>(null)
  const [leisureDraft, setLeisureDraft] = useState<[number, number][] | null>(
    null,
  )
  const leisureLine = leisureDraft ?? leisure?.coordinates ?? null
  const leisureRef = useRef({ line: leisureLine, draft: Boolean(leisureDraft) })
  leisureRef.current = { line: leisureLine, draft: Boolean(leisureDraft) }
  const shownFlagRef = useRef<RouteFlag | null>(null)
  shownFlagRef.current = shownFlag

  // 3. EFFECTS: code that runs when certain values change.

  // Ask the backend for a route (or, through the day, all of the day's routes) when the points or any option change.
  useEffect(() => {
    if (!start || !end) {
      return
    }
    const controller = new AbortController()
    setLoading(true)
    const request = { from: start, to: end, options }

    // Wait 300 ms after the last change, so dragging a slider sends one request, not dozens.
    const timer = setTimeout(() => {
      ;(dayMode
        ? fetchRouteDay(request, controller.signal).then(setDay)
        : fetchRouteComparison(request, controller.signal).then(setResult)
      )
        .then(() => setError(null))
        .catch(err => {
          if (err.name !== 'AbortError') {
            setResult(null)
            setDay(null)
            setError(err.message)
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setLoading(false)
          }
        })
    }, 300)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // routeVersion: a closure was reported or answered, so the route may change.
  }, [start, end, options, dayMode, reports.routeVersion])

  // Ask for the route's hills when "Show hills" is on and the points or options change.
  useEffect(() => {
    if (!showHills || !start || !end) {
      setGrade(null)
      return
    }
    const controller = new AbortController()
    const timer = setTimeout(() => {
      fetchRouteGrade(
        { from: start, to: end, options: tripOptions },
        controller.signal,
      )
        .then(data => {
          setGrade(data)
          setGradeError(null)
        })
        .catch(err => {
          if (err.name === 'AbortError') {
            return
          }
          setGrade(null)
          // 503: this backend has no elevation data; anything else: show the backend's message.
          setGradeError(
            err.status === 503
              ? t('greenest.planTrip.hills.unavailable')
              : err.message,
          )
        })
    }, 300)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [showHills, start, end, tripOptions, t])

  // The parking rules change rarely: load them once, the first time a trip is shown.
  useEffect(() => {
    if (!sharingTrip.trip || fences) {
      return
    }
    const controller = new AbortController()
    fetchGeofencing(controller.signal)
      .then(setFences)
      // Without them the trip still shows, only the coloured zones are missing.
      .catch(() => undefined)
    return () => controller.abort()
  }, [sharingTrip.trip, fences])

  // Draw (or clear) the leisure route or upload, and bring all of it into view.
  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }
    drawLeisure(map, leisureLine, Boolean(leisureDraft))
    if (leisureLine && leisureLine.length >= 2) {
      map.fitBounds(lineBounds(leisureLine), { padding: 60, maxZoom: 15 })
    }
  }, [leisureLine, leisureDraft])

  // Draw (or clear) the hills whenever they change.
  useEffect(() => {
    if (mapRef.current) {
      drawGrade(mapRef.current, grade)
    }
  }, [grade])

  // Draw (or clear) the two lines whenever a new result arrives; an open stretch popup belongs to the old one.
  useEffect(() => {
    if (mapRef.current) {
      drawRoutes(mapRef.current, shown)
      drawSegments(mapRef.current, shown)
      closeSegmentPopup()
    }
  }, [shown])

  // The chosen "Why this route?" row's stretches.
  useEffect(() => {
    if (mapRef.current) {
      highlightFlag(mapRef.current, shownFlag)
    }
  }, [shownFlag])

  // A clicked row zooms out to its stretches if some are off screen.
  useEffect(() => {
    const map = mapRef.current
    const current = resultRef.current
    if (!map || !current || !pinnedFlag) {
      return
    }
    const bounds = flagBounds(current, pinnedFlag)
    const view = map.getBounds()
    if (
      bounds &&
      !(
        view.contains(bounds.getSouthWest()) &&
        view.contains(bounds.getNorthEast())
      )
    ) {
      map.fitBounds(bounds.extend(view), {
        padding: 60,
        maxZoom: map.getZoom(),
      })
    }
  }, [pinnedFlag])

  // Esc lets go of the clicked row.
  useEffect(() => {
    if (!pinnedFlag) {
      return
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setPinnedFlag(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [pinnedFlag])

  // Riders' reports on the map.
  useEffect(() => {
    if (mapRef.current) {
      drawReports(
        mapRef.current,
        reports.closures,
        reports.mapping,
        showReports,
      )
    }
  }, [reports.closures, reports.mapping, showReports])

  // The streets or footways picked for the report.
  useEffect(() => {
    if (mapRef.current) {
      drawReportPicks(mapRef.current, picks, reportKind)
    }
  }, [picks, reportKind])

  // A pin where the rider is reporting another map mistake.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !draft || reportKind !== 'other') {
      return
    }
    const marker = new maplibregl.Marker({
      color: '#5e35b1',
      scale: 0.8,
    })
      .setLngLat(draft)
      .addTo(map)
    return () => {
      marker.remove()
    }
  }, [draft, reportKind])

  // Shared vehicles and parking zones.
  useEffect(() => {
    if (mapRef.current) {
      drawSharing(mapRef.current, sharing.vehicles, sharing.zones)
    }
    if (!sharing.vehicles) {
      popupRef.current?.remove()
    }
  }, [sharing.vehicles, sharing.zones])

  // The rented-vehicle trip; your route and the shortest fade meanwhile.
  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }
    drawTrip(map, sharingTrip.trip, fences, sharingTrip.plainTrip)
    fadeRoutes(map, Boolean(sharingTrip.trip))
  }, [sharingTrip.trip, sharingTrip.plainTrip, fences])

  // Pins where to pick the vehicle up (①) and where to leave it (P), each with
  // a popup on hover (mouse) or tap (touch).
  useEffect(() => {
    const map = mapRef.current
    const trip = sharingTrip.trip
    if (!map || !trip) {
      return
    }
    const s = (key: string, values?: Record<string, unknown>) =>
      t(`greenest.planTrip.sharing.${key}`, values)
    const minutes = (seconds: number) => Math.max(1, Math.round(seconds / 60))
    const [walk1, ride, walk2] = trip.legs
    const v = trip.vehicle.properties
    const rp = trip.return_point.properties
    const url = safeRentUrl(v.rent_url)
    const price = priceFor(v.price, trip.ride_s)

    const pickUp: PinInfo = {
      badge: '1',
      color: VEHICLE_COLORS[v.vehicle],
      title: s('pin.pickUp', {
        vehicle: `${v.provider} ${s(`vehicle.${v.vehicle}`)}`,
      }),
      battery: v.battery_pct,
      lines: [
        s('pin.walkThere', {
          m: Math.round(walk1.properties.length_m),
          min: minutes(walk1.properties.duration_s),
        }),
        ...(v.price ? [localPrice(v.price, t, i18n.language)] : []),
        ...(price !== null
          ? [
              s('pin.rideCost', {
                min: minutes(trip.ride_s),
                price: price.toLocaleString(i18n.language, {
                  style: 'currency',
                  currency: 'EUR',
                }),
              }),
            ]
          : []),
      ],
      rent: url
        ? { url, label: s('rentThis', { provider: v.provider }) }
        : undefined,
    }
    const leave: PinInfo = {
      badge: 'P',
      color: WALK_COLOR,
      square: true,
      title: s('pin.leave'),
      lines: [
        rp.rule === 'parking_zone' && rp.name
          ? s('pin.atZone', { zone: rp.name })
          : rp.at_destination
            ? s('pin.atEnd')
            : s('pin.outside', { vehicle: s(`vehicle.${v.vehicle}`) }),
        s('pin.rideHere', {
          km: (ride.properties.length_m / 1000).toLocaleString(i18n.language, {
            maximumFractionDigits: 1,
          }),
          min: minutes(trip.ride_s),
        }),
        ...(walk2.properties.length_m > 0
          ? [
              s('pin.walkOn', {
                m: Math.round(walk2.properties.length_m),
                min: minutes(walk2.properties.duration_s),
              }),
            ]
          : []),
      ],
    }

    const [pickUpLng, pickUpLat] = trip.vehicle.geometry.coordinates
    const [leaveLng, leaveLat] = trip.return_point.geometry.coordinates
    const pins: Array<[PinInfo, LngLat]> = [
      [pickUp, [pickUpLng, pickUpLat]],
      [leave, [leaveLng, leaveLat]],
    ]
    const markers = pins.map(([info, at]) => {
      const marker = new maplibregl.Marker({
        element: tripPin(info.badge, info.color, info.square),
      })
        .setLngLat(at)
        .addTo(map)
      const popup = new maplibregl.Popup({
        className: 'greenest-popup',
        // Don't focus the rent link on open: it would show a focus ring on every hover.
        focusAfterOpen: false,
        offset: 16,
        maxWidth: '260px',
      }).setDOMContent(pinPopup(info))
      attachPinPopup(marker, map, popup)
      return { marker, popup }
    })
    return () =>
      markers.forEach(({ marker, popup }) => {
        popup.remove()
        marker.remove()
      })
  }, [sharingTrip.trip, t, i18n.language])

  // A start set any other way answers the location message.
  useEffect(() => setLocateError(null), [start])

  // Green pin at the start, red pin at the destination. Drag a pin to move the
  // point; while it is dragged the map stays put. The cleanup removes the pin
  // when its point changes or is reset.
  useEffect(() => {
    const map = mapRef.current
    if (!map || !start) {
      return
    }
    const marker = endpointPin(map, start, '#1a7f37', t('greenest.planTrip.start'), point => {
      setStart(point)
      setStartLabel(formatPoint(point))
    })
    return () => {
      marker.remove()
    }
  }, [start, t])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !end) {
      return
    }
    const marker = endpointPin(map, end, '#b3261e', t('greenest.planTrip.destination'), point => {
      setEnd(point)
      setEndLabel(formatPoint(point))
    })
    return () => {
      marker.remove()
    }
  }, [end, t])

  // 4. HANDLERS: functions called by clicks and buttons.

  function segmentLabels(): SegmentLabels {
    const g = (key: string, values?: Record<string, unknown>) =>
      t(`greenest.planTrip.segment.${key}`, values)
    return {
      route: (kind: RouteKind) => t(`greenest.planTrip.routes.${kind}`),
      unnamed: g('unnamed'),
      way: kind => g(`ways.${kind}`),
      beside: way => g('beside', { way }),
      length: m => g('length', { m }),
      row: key => g(`rows.${key}`),
      notMeasured: g('notMeasured'),
      yes: g('yes'),
      no: g('no'),
      number: (n, digits) =>
        n.toLocaleString(i18n.language, {
          minimumFractionDigits: digits,
          maximumFractionDigits: digits,
        }),
    }
  }

  function closeSegmentPopup() {
    segmentPopupRef.current?.popup.remove()
    segmentPopupRef.current = null
    if (mapRef.current) {
      markSegment(mapRef.current, null)
    }
  }

  /**
   * Shows what the stretch of a route under `point` is like: on hover until the
   * mouse leaves it, or (pinned) after a click or tap until closed. Returns
   * whether a stretch was there.
   */
  function showSegment(
    map: maplibregl.Map,
    point: maplibregl.PointLike,
    at: maplibregl.LngLatLike,
    pinned: boolean,
  ): boolean {
    const current = resultRef.current
    const hit = segmentAt(map, point, current)
    if (!hit || !current) {
      return false
    }
    const open = segmentPopupRef.current
    if (open?.pinned && !pinned) {
      return true // a clicked stretch stays until it's closed
    }
    open?.popup.remove()
    const popup = new maplibregl.Popup({
      className: 'greenest-popup',
      closeButton: pinned,
      closeOnClick: false,
      focusAfterOpen: false,
      offset: 12,
      maxWidth: '260px',
    })
      .setLngLat(at)
      .setDOMContent(
        segmentPopup(
          hit.kind,
          hit.segment,
          current.route.properties,
          segmentLabels(),
          // Only once clicked (a hovering popup can't be clicked) and from a backend that names the segments.
          pinned && hit.segment.segments?.length
            ? {
                label: t('greenest.planTrip.reports.reportStretch'),
                onClick: () => reportStretch(hit.segment, hit.line),
              }
            : undefined,
        ),
      )
      .addTo(map)
    const entry = { popup, pinned }
    popup.on('close', () => {
      if (segmentPopupRef.current === entry) {
        segmentPopupRef.current = null
        markSegment(map, null)
      }
    })
    segmentPopupRef.current = entry
    markSegment(map, hit.line)
    return true
  }

  /** Hovering a route line shows its stretch (once per map: the listeners outlive style reloads). */
  function bindSegmentHover(map: maplibregl.Map) {
    if (segmentEventsRef.current) {
      return
    }
    segmentEventsRef.current = true
    map.on('mousemove', SEGMENT_HIT_LAYER, e => {
      map.getCanvas().style.cursor = 'pointer'
      showSegment(map, e.point, e.lngLat, false)
    })
    map.on('mouseleave', SEGMENT_HIT_LAYER, () => {
      map.getCanvas().style.cursor = ''
      if (!segmentPopupRef.current?.pinned) {
        closeSegmentPopup()
      }
    })
  }

  /** Opens a popup if the click hit a shared vehicle or zone; returns whether it did. */
  function openSharingPopup(map: maplibregl.Map, point: LngLat): boolean {
    const layers = CLICKABLE_SHARING_LAYERS.filter(id => map.getLayer(id))
    if (!layers.length) {
      return false
    }
    const { x, y } = map.project(point)
    const r = CLICK_TOLERANCE_PX
    const [hit] = map.queryRenderedFeatures(
      [
        [x - r, y - r],
        [x + r, y + r],
      ],
      { layers },
    )
    if (!hit || hit.geometry.type !== 'Point') {
      return false
    }
    const s = (key: string, values?: Record<string, unknown>) =>
      t(`greenest.planTrip.sharing.${key}`, values)
    const bikes = (count: number) => s('zoneBikes', { count })
    const scooters = (count: number) => s('zoneScooters', { count })
    const content = sharingPopup(hit.layer.id, hit.properties, {
      vehicle: kind => s(`vehicle.${kind}`),
      away: m => s('away', { m }),
      range: km => s('range', { km }),
      price: price => localPrice(price, t, i18n.language),
      rent: provider => s('rent', { provider }),
      zoneSpaces: (b, sc) =>
        b != null && sc != null
          ? s('zoneSpaces.both', { bikes: bikes(b), scooters: scooters(sc) })
          : s('zoneSpaces.one', {
              what: b != null ? bikes(b) : scooters(sc ?? 0),
            }),
      zoneCounts: (provider, b, sc) =>
        s('zoneCounts', { provider, bikes: bikes(b), scooters: scooters(sc) }),
    })
    popupRef.current?.remove()
    popupRef.current = new maplibregl.Popup({
      className: 'greenest-popup',
      // Don't focus the rent link on open: it would show a focus ring on every hover.
      focusAfterOpen: false,
      offset: 10,
      maxWidth: '260px',
    })
      .setLngLat(hit.geometry.coordinates as LngLat)
      .setDOMContent(content)
      .addTo(map)
    return true
  }

  /** The thank-you line after a closure report or answer, from the street's new status. */
  function closureThanks(
    status: ClosureStatus,
    count: number,
    stillClosed?: boolean,
  ): string {
    const k = (key: string, values?: Record<string, unknown>) =>
      t(`greenest.planTrip.reports.thanks.${key}`, values)
    if (status === 'open') {
      return k('lifted')
    }
    if (stillClosed !== undefined) {
      return k(stillClosed ? 'stillClosed' : 'openAgain')
    }
    return status === 'closed' ? k('closed', { count }) : k('reported')
  }

  /** One tap on a known closure: still closed (a new report) or open again (two riders lift it). */
  function answerClosure(segment: string, stillClosed: boolean) {
    popupRef.current?.remove()
    reports
      .answer(segment, stillClosed)
      .then(f =>
        setReportStatus(
          closureThanks(f.properties.status, f.properties.reports, stillClosed),
        ),
      )
      .catch(err => setReportStatus(err.message))
  }

  /** Another kind of report, or back to planning the route: what was picked or marked goes. */
  function changeReportKind(kind: ReportKind | null) {
    setReportKind(kind)
    setDraft(null)
    setPicks([])
    setPickError(null)
  }

  /** Adds a pick, or removes it when it was picked already (a second click on the same street). */
  function togglePick(pick: ReportPick) {
    setPicks(current =>
      current.some(p => p.key === pick.key)
        ? current.filter(p => p.key !== pick.key)
        : [...current, pick],
    )
  }

  /** What riders already reported on any of `segments`, from the closures on the map. */
  function knownStatus(segments: string[]): ClosureStatus | null {
    return (
      reports.closures?.features.find(f =>
        segments.includes(f.properties.segment),
      )?.properties.status ?? null
    )
  }

  /** A click while reporting a closed street or a footway: picks (or unpicks) the one under it. */
  function pickAt(point: LngLat, kind: 'closure' | 'rideable') {
    setPending(n => n + 1)
    setPickError(null)
    const r = (key: string) => t(`greenest.planTrip.reports.pick.${key}`)
    const lookup: Promise<ReportPick> =
      kind === 'closure'
        ? fetchReportSegment(point).then(
            ({ geometry, properties: p }: StreetSegmentFeature) => ({
              key: p.segment,
              name: p.name,
              length_m: p.length_m,
              geometry,
              segments: [p.segment],
              status: p.status,
            }),
          )
        : fetchReportFootway(point).then(
            ({ geometry, properties: p }: FootwayFeature) => ({
              key: `way-${p.osm_way_id}`,
              name: p.name,
              length_m: p.length_m,
              geometry,
              wayId: p.osm_way_id,
            }),
          )
    lookup
      .then(pick => {
        // The rider may have switched to another kind meanwhile.
        if (reportKindRef.current === kind) {
          togglePick(pick)
        }
      })
      .catch(err => {
        if (reportKindRef.current === kind) {
          setPickError(
            err.status === 404
              ? r('noFootway')
              : err.status === 400
                ? r('noStreet')
                : err.message,
          )
        }
      })
      .finally(() => setPending(n => n - 1))
  }

  /** "Report closed here" in a route stretch's popup: the whole stretch, all its segments. */
  function reportStretch(segment: RouteSegment, line: LineString) {
    closeSegmentPopup()
    changeReportKind('closure')
    setPicks([
      {
        key: `stretch-${segment.segments.join(',')}`,
        name: segment.name,
        length_m: segment.length_m,
        geometry: line,
        segments: segment.segments,
        status: knownStatus(segment.segments),
      },
    ])
  }

  /** The middle of a picked line, where a footway report is placed on the map. */
  function middle(geometry: ReportPick['geometry']): LngLat {
    const line =
      geometry.type === 'LineString'
        ? geometry.coordinates
        : geometry.coordinates[0]
    return line[Math.floor(line.length / 2)] as LngLat
  }

  /** Sends the report; rejects with the backend's message. */
  async function submitReport(note: string, until: string): Promise<string> {
    const text = note || undefined
    let message = ''
    if (reportKind === 'closure') {
      // A segment picked by a click and again in a route stretch is reported once.
      const segments = Array.from(new Set(picks.flatMap(p => p.segments ?? [])))
      const states = await reports.sendClosures(
        segments,
        text,
        until || undefined,
      )
      message =
        states.length === 1
          ? closureThanks(
              states[0].properties.status,
              states[0].properties.reports,
            )
          : t('greenest.planTrip.reports.thanks.closures', {
              count: states.length,
            })
    } else if (reportKind === 'rideable') {
      await reports.sendMapping(
        picks.map(p => middle(p.geometry)),
        'rideable',
        text,
        picks.map(p => p.wayId as number),
      )
      message = t('greenest.planTrip.reports.thanks.rideable', {
        count: picks.length,
      })
    } else if (reportKind === 'other' && draft) {
      await reports.sendMapping([draft], 'other', text)
      message = t('greenest.planTrip.reports.thanks.other')
    }
    setDraft(null)
    setPicks([])
    return message
  }

  /** Opens a popup if the click hit a closure or a mapping report; returns whether it did. */
  function openReportPopup(map: maplibregl.Map, point: LngLat): boolean {
    const layers = CLICKABLE_REPORT_LAYERS.filter(id => map.getLayer(id))
    if (!showReports || !layers.length) {
      return false
    }
    const { x, y } = map.project(point)
    const r = CLICK_TOLERANCE_PX
    const [hit] = map.queryRenderedFeatures(
      [
        [x - r, y - r],
        [x + r, y + r],
      ],
      { layers },
    )
    if (!hit) {
      return false
    }
    const content = reportPopup(
      hit.layer.id,
      hit.properties,
      {
        closure: p => closureText(p, t, i18n.language),
        stillClosed: t('greenest.planTrip.reports.stillClosed'),
        openAgain: t('greenest.planTrip.reports.openAgain'),
        mappingTitle: p =>
          t(`greenest.planTrip.reports.mappingTitle.${p.kind}`),
      },
      answerClosure,
    )
    popupRef.current?.remove()
    popupRef.current = new maplibregl.Popup({
      className: 'greenest-popup',
      focusAfterOpen: false,
      offset: 10,
      maxWidth: '280px',
    })
      // A mapping report opens at its dot, a closure where it was clicked.
      .setLngLat(
        hit.geometry.type === 'Point'
          ? (hit.geometry.coordinates as LngLat)
          : point,
      )
      .setDOMContent(content)
      .addTo(map)
    return true
  }

  function handleMapClick(point: LngLat) {
    const map = mapRef.current
    // Reporting (after "Report a problem"): the click picks the street or footway there, or marks the spot of
    // another mistake; the form is in that panel.
    if (reportKind === 'other') {
      setDraft(point)
      return
    }
    if (reportKind) {
      pickAt(point, reportKind)
      return
    }
    // A known closure or report opens its popup.
    if (map && openReportPopup(map, point)) {
      return
    }
    if (map && openSharingPopup(map, point)) {
      return
    }
    // A click on a route line explains that stretch instead of moving the destination there.
    if (map && showSegment(map, map.project(point), point, true)) {
      return
    }
    // The first click beside the line only closes the stretch popup.
    if (segmentPopupRef.current) {
      closeSegmentPopup()
      return
    }
    if (!start) {
      setStart(point)
      setStartLabel(formatPoint(point))
    } else {
      setEnd(point)
      setEndLabel(formatPoint(point))
    }
  }

  /** A place picked from the search list: set the point and move the map there. */
  function pickPlace(which: 'start' | 'end', point: LngLat, label: string) {
    if (which === 'start') {
      setStart(point)
      setStartLabel(label)
    } else {
      setEnd(point)
      setEndLabel(label)
    }
    const map = mapRef.current
    const other = which === 'start' ? end : start
    if (!map) {
      return
    }
    if (other) {
      // Both points known: show them both.
      map.fitBounds(new maplibregl.LngLatBounds(point, point).extend(other), {
        padding: 80,
        maxZoom: 16,
      })
    } else {
      map.flyTo({ center: point, zoom: Math.max(map.getZoom(), 15) })
    }
  }

  /** "Use my location": the device's position becomes the start, if it is in Heilbronn. */
  function locateStart() {
    const l = (key: string) => t(`greenest.planTrip.locate.${key}`)
    // Also missing on plain http (except localhost): browsers only locate on secure pages.
    if (!('geolocation' in navigator) || !window.isSecureContext) {
      setLocateError(l('unsupported'))
      return
    }
    setLocating(true)
    setLocateError(null)
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false)
        const point: LngLat = [coords.longitude, coords.latitude]
        const [west, south, east, north] = HEILBRONN_BBOX
        if (
          point[0] < west ||
          point[0] > east ||
          point[1] < south ||
          point[1] > north
        ) {
          setLocateError(l('outside'))
          return
        }
        pickPlace('start', point, l('here'))
      },
      err => {
        setLocating(false)
        setLocateError(
          l(err.code === err.PERMISSION_DENIED ? 'denied' : 'failed'),
        )
      },
      LOCATE_OPTIONS,
    )
  }

  // Opening a saved route from the Profile tab (/plan-trip?saved=<id>).
  const savedRouteError = useSavedRouteFromUrl(mapReady, route => {
    const from: LngLat = [route.start_lon, route.start_lat]
    const to: LngLat = [route.end_lon, route.end_lat]
    setOptions(fromSavedOptions(route.options))
    setStart(from)
    setStartLabel(route.start_label ?? formatPoint(from))
    setEnd(to)
    setEndLabel(route.end_label ?? formatPoint(to))
    mapRef.current?.fitBounds(
      new maplibregl.LngLatBounds(from, from).extend(to),
      { padding: 80, maxZoom: 16 },
    )
  })

  // A leisure route from Highlights, the Profile tab or a shared link (/plan-trip?route=<id>).
  function openLeisure(route: CommunityRoute) {
    setLeisureDraft(null)
    setLeisure(route)
  }
  const communityFromUrl = useCommunityRouteFromUrl(mapReady, openLeisure)

  // "Dorthin fahren": the route's start becomes the destination; the rider's start stays.
  function rideToLeisure(route: CommunityRoute) {
    const point = route.coordinates[0]
    setEnd(point)
    setEndLabel(route.name)
  }

  function handleReset() {
    setStart(null)
    setEnd(null)
    setStartLabel('')
    setEndLabel('')
    setResult(null)
    setDay(null)
    setError(null)
    setLoading(false)
    setGrade(null)
    setGradeError(null)
    setPinnedFlag(null)
    setPreviewFlag(null)
    changeReportKind(null)
    setReportStatus(null)
    setLocateError(null)
  }

  // 5. RENDER: what appears on the page.
  return (
    // data-workspace: on wide screens the page fills the window and doesn't
    // scroll; the cards column and the map each keep their own height.
    <div
      className="mx-auto flex min-h-0 w-full max-w-[1920px] flex-1 flex-col gap-4 px-4 py-4 md:px-8"
      data-workspace
    >
      <PageIntro
        subtitle={t('greenest.planTrip.subtitle')}
        title={t('greenest.planTrip.title')}
      />
      <div className="grid flex-1 grid-cols-1 gap-4 lg:min-h-0 lg:grid-cols-[24rem_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)]">
        <div className="flex flex-col gap-4 lg:min-h-0 lg:overflow-y-auto lg:overscroll-contain lg:pb-1 lg:pr-2">
          {leisure && (
            <LeisureRouteCard
              onClose={() => setLeisure(null)}
              onDeleted={() => setLeisure(null)}
              onRideThere={() => rideToLeisure(leisure)}
              route={leisure}
            />
          )}
          {communityFromUrl.error && (
            <p
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800"
              role="alert"
            >
              {communityFromUrl.error}
            </p>
          )}
          <TripForm
            dayMode={dayMode}
            daySlider={
              start && end ? (
                <DaySlider
                  index={stopIndex}
                  onIndexChange={pickStop}
                  stops={stops}
                />
              ) : (
                <span className="text-xs text-leaf-muted">
                  {t('greenest.planTrip.day.needRoute')}
                </span>
              )
            }
            endLabel={endLabel}
            loading={loading}
            locateError={locateError}
            locating={locating}
            onDayModeChange={setDayMode}
            onEndLabelChange={setEndLabel}
            onLocate={locateStart}
            onOptionsChange={setOptions}
            onPickEnd={(point, label) => pickPlace('end', point, label)}
            onPickStart={(point, label) => pickPlace('start', point, label)}
            onReset={handleReset}
            onStartLabelChange={setStartLabel}
            options={options}
            startLabel={startLabel}
          />
          {error && (
            <p
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800"
              role="alert"
            >
              {error}
            </p>
          )}
          <RouteComparisonCard
            focus={{
              shown: shownFlag,
              pinned: pinnedFlag,
              onPreview: setPreviewFlag,
              onToggle: flag =>
                setPinnedFlag(current => (current === flag ? null : flag)),
            }}
            paused={Boolean(sharingTrip.trip)}
            result={shown}
          />
          <SaveRouteButton
            end={end}
            endLabel={endLabel}
            openError={savedRouteError}
            options={options}
            result={result}
            start={start}
            startLabel={startLabel}
          />
          <ContributeRouteCard
            onPreview={setLeisureDraft}
            onPublished={openLeisure}
            startOpen={communityFromUrl.contribute}
          />
          <ReportsCard
            error={reports.error}
            near={nearClosure}
            onAnswer={answerClosure}
            onShowChange={setShowReports}
            onSkip={reports.skip}
            show={showReports}
            status={reportStatus}
          />
          <SharingCard
            error={sharing.error}
            hasRoute={Boolean(start && end)}
            hasStart={Boolean(start)}
            onShowChange={setShowSharing}
            onTripOnChange={setTripOn}
            onTripVehicleChange={setTripVehicle}
            onVehicleChange={setSharingVehicle}
            plainTrip={sharingTrip.plainTrip}
            show={showSharing}
            trip={sharingTrip.trip}
            tripError={sharingTrip.error}
            tripLoading={sharingTrip.loading}
            tripOn={tripOn}
            tripVehicle={tripVehicle}
            vehicle={sharingVehicle}
            vehicles={sharing.vehicles}
            zones={sharing.zones}
          />
          <GradeCard
            error={gradeError}
            grade={grade}
            hasRoute={Boolean(start && end)}
            onShowChange={setShowHills}
            show={showHills}
          />
        </div>
        <section className="relative h-[60vh] min-h-[420px] overflow-hidden rounded-3xl border border-leaf-sand shadow-soft lg:h-auto lg:min-h-0">
          <BaseMap
            ariaLabel={t('greenest.planTrip.mapLabel')}
            onClick={handleMapClick}
            onLoad={map => {
              mapRef.current = map
              // Coming from Highlights ("Auf Karte zeigen": that place is the destination) or from
              // a shared trip link (start, destination and options).
              const shared = readTripLink(
                new URLSearchParams(window.location.search),
              )
              if (shared) {
                const { start: from, end: to } = shared
                setOptions(shared.options)
                if (from) {
                  setStart(from)
                  setStartLabel(shared.startLabel || formatPoint(from))
                }
                if (to) {
                  setEnd(to)
                  setEndLabel(shared.endLabel || formatPoint(to))
                }
                if (from && to) {
                  map.fitBounds(
                    new maplibregl.LngLatBounds(from, from).extend(to),
                    { padding: 80, maxZoom: 16, duration: 0 },
                  )
                } else {
                  map.jumpTo({ center: (from ?? to) as LngLat, zoom: 15 })
                }
                window.history.replaceState(null, '', window.location.pathname)
              }
              // Bottom to top: riders' leisure route, routes, hills, highlighted stretches, riders'
              // reports, shared vehicles, the rented-vehicle trip.
              drawLeisure(
                map,
                leisureRef.current.line,
                leisureRef.current.draft,
              )
              drawRoutes(map, resultRef.current)
              drawGrade(map, gradeRef.current)
              drawSegments(map, resultRef.current)
              highlightFlag(map, shownFlagRef.current)
              bindSegmentHover(map)
              drawReports(
                map,
                reportsRef.current.closures,
                reportsRef.current.mapping,
                reportsRef.current.show,
              )
              drawReportPicks(map, picksRef.current, reportKindRef.current)
              drawSharing(
                map,
                sharingRef.current.vehicles,
                sharingRef.current.zones,
              )
              drawTrip(
                map,
                tripRef.current,
                fencesRef.current,
                plainTripRef.current,
              )
              fadeRoutes(map, Boolean(tripRef.current))
              setMapReady(true)
            }}
          />
          <ReportProblem
            draft={draft}
            kind={reportKind}
            onKindChange={changeReportKind}
            onRemovePick={key =>
              setPicks(current => current.filter(p => p.key !== key))
            }
            onSubmit={submitReport}
            pickError={pickError}
            picking={pending > 0}
            picks={picks}
          />
        </section>
      </div>
    </div>
  )
}
