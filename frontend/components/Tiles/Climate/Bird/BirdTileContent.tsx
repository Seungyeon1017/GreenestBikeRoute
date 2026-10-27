'use client'

import { Spacer } from '@/components/Elements/Spacer'
import useBirdiary, { BirdDayCount } from '@/hooks/useBirdiary'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { isEuropeanBird } from './europeanBirdFilter'

interface BirdTileContentProps {
  stationId: string
}

export default function BirdTileContent({ stationId }: BirdTileContentProps) {
  const { data, isLoading } = useBirdiary(stationId)
  const { t } = useTranslation()

  const latestVideo = useMemo(() => {
    if (!data) {
      return null
    }

    // Find the latest movement with a video and detections
    const movement = data.lastMovement ?? data.movements?.[0]
    if (movement?.video) {
      return movement
    }
    // Fallback: search through movements for one with a video
    return data.movements?.find(m => m.video && m.detections.length > 0)
  }, [data])

  const recentDays = useMemo(() => {
    if (!data?.count) {
      return []
    }

    const entries = Object.entries(data.count) as [string, BirdDayCount][]
    return entries.sort(([a], [b]) => b.localeCompare(a)).slice(0, 7)
  }, [data])

  const filteredDaySum = (day: BirdDayCount): number =>
    day.birds
      .filter(b => isEuropeanBird(b.latinName))
      .reduce((s, b) => s + b.amount, 0)

  const totalBirdsLast7Days = useMemo(() => {
    return recentDays.reduce((sum, [, day]) => sum + day.sum, 0)
  }, [recentDays])

  const topSpecies = useMemo(() => {
    if (!data?.count) {
      return []
    }

    const speciesMap = new Map<
      string,
      { german: string; latin: string; count: number }
    >()

    for (const [, day] of Object.entries(data.count)) {
      for (const bird of (day as BirdDayCount).birds) {
        if (!isEuropeanBird(bird.latinName)) {
          continue
        }
        const key = bird.latinName
        const existing = speciesMap.get(key)
        const displayName = bird.germanName || bird.latinName
        if (existing) {
          existing.count += bird.amount
        } else {
          speciesMap.set(key, {
            german: displayName,
            latin: bird.latinName,
            count: bird.amount,
          })
        }
      }
    }

    return Array.from(speciesMap.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 5)
  }, [data])

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-climate border-t-transparent" />
      </div>
    )
  }

  if (!data) {
    return <p className="text-sm text-gray-500">{t('birdTile.noData')}</p>
  }

  const latestDetectionName =
    latestVideo?.detections?.[0]?.germanName ||
    latestVideo?.detections?.[0]?.latinName

  return (
    <div className="space-y-4">
      {/* Video + Stats side-by-side on larger screens */}
      <div className="flex flex-col gap-4 lg:flex-row">
        {/* Latest Video */}
        {latestVideo?.video && (
          <div className="overflow-hidden rounded-lg lg:w-1/2">
            <video
              autoPlay
              className="w-full rounded-lg"
              controls
              loop
              muted
              playsInline
              src={latestVideo.video}
            >
              <track kind="captions" />
            </video>
            {latestDetectionName && (
              <p className="mt-2 text-sm font-semibold text-climate">
                🐦 {t('birdTile.lastDetected')}: {latestDetectionName}
                {latestVideo.detections[0]?.score && (
                  <span className="ml-1 font-normal text-gray-500">
                    ({Math.round(latestVideo.detections[0].score * 100)}%
                    {' '}{t('birdTile.confidence')})
                  </span>
                )}
              </p>
            )}
          </div>
        )}

        {/* Stats + Top Species next to video */}
        <div
          className={`flex flex-col gap-3 ${latestVideo?.video ? 'lg:w-1/2' : 'w-full'}`}
        >
          {/* Stats Overview */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-white/60 p-3 text-center">
              <p className="text-2xl font-bold text-climate">
                {totalBirdsLast7Days}
              </p>
              <p className="text-xs text-gray-600">{t('birdTile.birdsLast7Days')}</p>
            </div>
            <div className="rounded-lg bg-white/60 p-3 text-center">
              <p className="text-2xl font-bold text-climate">
                {topSpecies.length}
              </p>
              <p className="text-xs text-gray-600">{t('birdTile.speciesDetected')}</p>
            </div>
          </div>

          {/* Top Species (shown next to video on lg) */}
          {topSpecies.length > 0 && (
            <div>
              <p className="mb-2 text-sm font-semibold text-climate">
                {t('birdTile.mostFrequentSpecies')}
              </p>
              <div className="space-y-1">
                {topSpecies.map(species => (
                  <div
                    className="flex items-center justify-between rounded-md bg-white/60 px-3 py-1.5"
                    key={species.latin}
                  >
                    <div>
                      <span className="text-sm font-medium">
                        {species.german}
                      </span>
                      <span className="ml-2 text-xs italic text-gray-400">
                        {species.latin}
                      </span>
                    </div>
                    <span className="text-sm font-bold text-climate">
                      {species.count}×
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <Spacer size="xs" />

      {/* Daily Breakdown */}
      {recentDays.length > 0 && (
        <div>
          <p className="mb-2 text-sm font-semibold text-climate">
            {t('birdTile.sightingsPerDay')}
          </p>
          <div className="space-y-1.5">
            {recentDays.map(([date, day]) => {
              const d = new Date(date + 'T00:00:00')
              const isToday = format(new Date(), 'yyyy-MM-dd') === date
              const label = isToday
                ? t('birdTile.today')
                : format(d, 'EEEE, dd. MMM', { locale: de })

              // const filteredSum = filteredDaySum(day)
              const maxCount = Math.max(
                ...recentDays.map(([, rd]) => rd.sum),
                1,
              )
              const barWidth = (day.sum / maxCount) * 100

              return (
                <div className="flex items-center gap-2" key={date}>
                  <span className="w-32 shrink-0 text-xs text-gray-600">
                    {label}
                  </span>
                  <div className="relative h-5 flex-1 overflow-hidden rounded-full bg-white/60">
                    <div
                      className="absolute inset-y-0 left-0 rounded-full bg-climate/70 transition-all"
                      style={{ width: `${barWidth}%` }}
                    />
                    <span className="relative z-10 flex h-full items-center px-2 text-xs font-medium">
                      {day.sum}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
