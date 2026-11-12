import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fetchTrainTrip } from '@/services/greenestApi'
import type {
  LngLat,
  RouteOptions,
  TrainDirection,
  TrainTrip,
  TransitStopProperties,
} from '@/types/greenest'

/**
 * What a train trip runs between. to_train: ride from `point` to a station and take the
 * train to `toStation`. from_train: take the train from `fromStation` and ride to `point`.
 * train: from `fromStation` to `toStation`, nothing to ride.
 */
export type TrainPlan = {
  direction: TrainDirection
  fromStation?: TransitStopProperties
  toStation?: TransitStopProperties
  point?: LngLat
}

/**
 * The trip with a train (/route/train) for `plan`, or nothing while it is null.
 * Asked again when the plan or the rider's options change.
 */
export function useTrainTrip(plan: TrainPlan | null, options: RouteOptions) {
  const { t } = useTranslation()
  const [trip, setTrip] = useState<TrainTrip | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const direction = plan?.direction
  const fromStation = plan?.fromStation
  const toStation = plan?.toStation
  const point = plan?.point

  useEffect(() => {
    const from = fromStation?.stop_id ?? point
    const to = toStation?.stop_id ?? point
    if (!direction || !from || !to) {
      setTrip(null)
      setError(null)
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    // Same 300 ms pause as the route, so a slider drag sends one request.
    const timer = setTimeout(() => {
      fetchTrainTrip(from, to, options, controller.signal)
        .then(data => {
          setTrip(data)
          setError(null)
        })
        .catch(err => {
          if (err.name === 'AbortError') {
            return
          }
          setTrip(null)
          setError(
            err.status === 503
              ? t('greenest.planTrip.train.unavailable')
              : err.status === 400 && err.message.includes('same station')
                ? t('greenest.planTrip.train.sameStation')
                : err.status === 400 && err.message.includes('no direct train')
                  ? t(`greenest.planTrip.train.noTrain.${direction}`, {
                      station: (toStation ?? fromStation)?.name,
                      from: fromStation?.name,
                      to: toStation?.name,
                    })
                  : err.message,
          )
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
  }, [direction, fromStation, toStation, point, options, t])

  return { trip, error, loading }
}
