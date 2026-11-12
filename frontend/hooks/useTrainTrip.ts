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
 * The bike + train trip (/route/train) while `on` is set, a station is picked and the
 * point of the ride is known: the start for to_train, the destination for from_train.
 * Asked again when the point, the station or the rider's options change.
 */
export function useTrainTrip(
  on: boolean,
  direction: TrainDirection,
  station: TransitStopProperties | null,
  point: LngLat | null,
  options: RouteOptions,
) {
  const { t } = useTranslation()
  const [trip, setTrip] = useState<TrainTrip | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!on || !station || !point) {
      setTrip(null)
      setError(null)
      setLoading(false)
      return
    }
    const controller = new AbortController()
    setLoading(true)
    // Same 300 ms pause as the route, so a slider drag sends one request.
    const timer = setTimeout(() => {
      fetchTrainTrip(
        direction,
        point,
        station.stop_id,
        options,
        controller.signal,
      )
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
              : err.status === 400 && err.message.includes('no direct train')
                ? t(`greenest.planTrip.train.noTrain.${direction}`, {
                    station: station.name,
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
  }, [on, direction, station, point, options, t])

  return { trip, error, loading }
}
