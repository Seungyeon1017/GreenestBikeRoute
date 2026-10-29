import { useCallback, useEffect, useState } from 'react'
import {
  confirmClosure,
  fetchClosures,
  fetchMappingReports,
  reportClosure,
  reportMapping,
} from '@/services/greenestApi'
import type {
  ClosureCollection,
  ClosureFeature,
  LngLat,
  MappingCollection,
  MappingKind,
} from '@/types/greenest'

/** Other riders' reports come in now and then: look again every 5 minutes. */
const REPORTS_REFRESH_MS = 5 * 60_000

/** How close (m) to the trip's start or end a closure must be for the "still closed?" question. */
export const ASK_NEAR_M = 300

/** A closure this browser answered isn't asked about again for a day. */
const ASK_AGAIN_MS = 24 * 3600_000

/**
 * An anonymous random id per browser, so one rider's repeated reports count once.
 * Undefined where the browser keeps no storage (the backend then counts by network).
 */
function reporterId(): string | undefined {
  try {
    let id = localStorage.getItem('reporterId')
    if (!id) {
      id =
        typeof crypto.randomUUID === 'function'
          ? crypto.randomUUID()
          : Math.random().toString(36).slice(2)
      localStorage.setItem('reporterId', id)
    }
    return id
  } catch {
    return undefined
  }
}

/** Closures this browser answered: segment → when. */
function answered(): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem('answeredClosures') || '{}')
  } catch {
    return {}
  }
}

function remember(segment: string) {
  try {
    localStorage.setItem(
      'answeredClosures',
      JSON.stringify({ ...answered(), [segment]: Date.now() }),
    )
  } catch {
    // No storage: the question may come again, nothing worse.
  }
}

/** Metres between two points (equirectangular, plenty for a few hundred metres). */
function distanceM([lng1, lat1]: LngLat, [lng2, lat2]: LngLat): number {
  const rad = Math.PI / 180
  const x = (lng2 - lng1) * rad * Math.cos(((lat1 + lat2) / 2) * rad)
  const y = (lat2 - lat1) * rad
  return Math.hypot(x, y) * 6_371_000
}

/**
 * The first closure within ASK_NEAR_M of the trip's start or end that this browser
 * hasn't answered in the last day: riders there know whether it is still closed,
 * and nobody else rides past it.
 */
export function closureNear(
  closures: ClosureCollection | null,
  points: LngLat[],
): ClosureFeature | null {
  if (!closures || !points.length) {
    return null
  }
  const done = answered()
  return (
    closures.features.find(
      f =>
        Date.now() - (done[f.properties.segment] ?? 0) > ASK_AGAIN_MS &&
        f.geometry.coordinates.some(c =>
          points.some(p => distanceM(p, c as LngLat) <= ASK_NEAR_M),
        ),
    ) ?? null
  )
}

/**
 * Riders' reports: closed streets and mapping mistakes. Loads them now and every
 * few minutes, and again after each report or answer. A closure report or answer
 * also bumps `routeVersion`, so the route is asked again (it reroutes around a new
 * closure); `skipped` changes when a "still closed?" question is put aside.
 */
export function useReports() {
  const [closures, setClosures] = useState<ClosureCollection | null>(null)
  const [mapping, setMapping] = useState<MappingCollection | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loads, setLoads] = useState(0)
  const [routeVersion, setRouteVersion] = useState(0)
  const [skipped, setSkipped] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const load = () =>
      Promise.all([
        fetchClosures(controller.signal),
        fetchMappingReports(controller.signal),
      ])
        .then(([c, m]) => {
          setClosures(c)
          setMapping(m)
          setError(null)
        })
        .catch(err => {
          if (err.name !== 'AbortError') {
            setError(err.message)
          }
        })
    load()
    const timer = setInterval(load, REPORTS_REFRESH_MS)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [loads, routeVersion])

  const sendClosure = useCallback(
    async (at: LngLat, note?: string, until?: string) => {
      const feature = await reportClosure(at, reporterId(), note, until)
      setRouteVersion(v => v + 1)
      return feature
    },
    [],
  )

  const sendMapping = useCallback(
    async (at: LngLat, kind: MappingKind, note?: string) => {
      const feature = await reportMapping(at, kind, reporterId(), note)
      setLoads(n => n + 1)
      return feature
    },
    [],
  )

  const answer = useCallback(async (segment: string, stillClosed: boolean) => {
    remember(segment)
    const feature = await confirmClosure(segment, stillClosed, reporterId())
    setRouteVersion(v => v + 1)
    return feature
  }, [])

  /** "Don't know": not asked again for a day. */
  const skip = useCallback((segment: string) => {
    remember(segment)
    setSkipped(n => n + 1)
  }, [])

  return {
    closures,
    mapping,
    error,
    routeVersion,
    skipped,
    sendClosure,
    sendMapping,
    answer,
    skip,
  }
}
