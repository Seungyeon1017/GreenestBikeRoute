import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  fetchSharedVehicles,
  fetchSharingTrip,
  fetchSharingZones,
} from '@/services/greenestApi'
import type {
  LngLat,
  RouteOptions,
  SharingTrip,
  SharingVehicleChoice,
  VehicleCollection,
  ZoneCollection,
} from '@/types/greenest'

/** The feed is at most a minute old, so asking more often brings nothing new. */
export const SHARING_REFRESH_MS = 60_000

/** 503 means the sharing feed is down: a short note instead of the technical message. */
function sharingError(
  err: { status?: number; message: string },
  t: (_k: string) => string,
) {
  return err.status === 503
    ? t('greenest.planTrip.sharing.unavailable')
    : err.message
}

/**
 * Shared vehicles and parking zones while `show` is on: loads now, again when the
 * start moves (closest first) or the vehicle kind changes, and every minute.
 * Nothing is downloaded while `show` is off.
 */
export function useSharedVehicles(
  show: boolean,
  vehicle: SharingVehicleChoice,
  start: LngLat | null,
) {
  const { t } = useTranslation()
  const [vehicles, setVehicles] = useState<VehicleCollection | null>(null)
  const [zones, setZones] = useState<ZoneCollection | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!show) {
      setVehicles(null)
      setZones(null)
      setError(null)
      return
    }
    const controller = new AbortController()
    const load = () =>
      Promise.all([
        fetchSharedVehicles(vehicle, start, controller.signal),
        fetchSharingZones(start, controller.signal),
      ])
        .then(([v, z]) => {
          setVehicles(v)
          setZones(z)
          setError(null)
        })
        .catch(err => {
          if (err.name !== 'AbortError') {
            setVehicles(null)
            setZones(null)
            setError(sharingError(err, t))
          }
        })
    load()
    const timer = setInterval(load, SHARING_REFRESH_MS)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [show, vehicle, start, t])

  return { vehicles, zones, error }
}

/**
 * The rider's settings switched off: what the shortest route is to /route/compare.
 * The departure time stays, but with shade and dark at 0 it changes nothing.
 */
function withoutSettings(options: RouteOptions): RouteOptions {
  return {
    ...options,
    bump: 0,
    danger: 0,
    pm: 0,
    stop: 0,
    bikeFriendly: 0,
    preferTime: false,
    shade: 0,
    dark: 0,
  }
}

/**
 * The trip with a rented vehicle (/route/sharing) while `on` is set and both points are:
 * walk to it, ride it with the rider's options, walk to the end. `plainTrip` is the
 * same request without any settings, to compare with (like the shortest route).
 */
export function useSharingTrip(
  on: boolean,
  vehicle: SharingVehicleChoice,
  start: LngLat | null,
  end: LngLat | null,
  options: RouteOptions,
) {
  const { t } = useTranslation()
  const [trip, setTrip] = useState<SharingTrip | null>(null)
  const [plainTrip, setPlainTrip] = useState<SharingTrip | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!on || !start || !end) {
      setTrip(null)
      setPlainTrip(null)
      setError(null)
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    // Same 300 ms pause as the route, so a slider drag sends one request.
    const timer = setTimeout(() => {
      Promise.all([
        fetchSharingTrip(
          { from: start, to: end, options },
          vehicle,
          controller.signal,
        ),
        fetchSharingTrip(
          { from: start, to: end, options: withoutSettings(options) },
          vehicle,
          controller.signal,
        ),
      ])
        .then(([withSettings, plain]) => {
          setTrip(withSettings)
          setPlainTrip(plain)
          setError(null)
        })
        .catch(err => {
          if (err.name !== 'AbortError') {
            setTrip(null)
            setPlainTrip(null)
            setError(sharingError(err, t))
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
  }, [on, vehicle, start, end, options, t])

  return { trip, plainTrip, error, loading }
}
