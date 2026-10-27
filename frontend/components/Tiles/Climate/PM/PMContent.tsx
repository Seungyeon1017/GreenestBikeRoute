'use client'

import useParticulateMatter from '@/hooks/useParticulateMatter'
import type { PMType } from '@/hooks/useParticulateMatter'
import { useState } from 'react'
import PMMap, { PM_THRESHOLDS } from './PMMap'

const PM_OPTIONS: { key: PMType; label: string }[] = [
  { key: 'PM1', label: 'PM1' },
  { key: 'PM25', label: 'PM2.5' },
  { key: 'PM4', label: 'PM4' },
  { key: 'PM10', label: 'PM10' },
]

interface PMContentProps {
  grouptag: string
}

export default function PMContent({ grouptag }: PMContentProps) {
  const { stations, isLoading } = useParticulateMatter(grouptag)
  const [activePM, setActivePM] = useState<PMType>('PM25')

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-climate border-t-transparent" />
      </div>
    )
  }

  const hasAnyData = stations.some(s => Object.keys(s.measurements).length > 0)

  return (
    <div className="space-y-4">
      {/* PM type switcher */}
      <div className="flex flex-wrap items-center gap-2">
        {PM_OPTIONS.map(opt => (
          <button
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              activePM === opt.key
                ? 'bg-climate text-white'
                : 'bg-white/60 text-gray-600 hover:bg-white/80'
            }`}
            key={opt.key}
            onClick={() => setActivePM(opt.key)}
            type="button"
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Full-width map */}
      {stations.length > 0 ? (
        <PMMap activePM={activePM} stations={stations} />
      ) : (
        <div className="flex min-h-[200px] items-center justify-center rounded-lg bg-white/60">
          <p className="text-sm text-gray-500">Keine Stationen gefunden.</p>
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-gray-500">µg/m³:</span>
        {PM_THRESHOLDS.filter(t => t.max !== Infinity).map(t => (
          <div className="flex items-center gap-1" key={t.label}>
            <span
              className="inline-block h-3 w-3 rounded-full"
              style={{ backgroundColor: t.color }}
            />
            <span className="text-xs text-gray-600">≤ {t.max}</span>
          </div>
        ))}
        <div className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ backgroundColor: '#ef4444' }}
          />
          <span className="text-xs text-gray-600">&gt; 50</span>
        </div>
        <div className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ backgroundColor: '#9ca3af' }}
          />
          <span className="text-xs text-gray-600">Keine Daten</span>
        </div>
      </div>

      {/* Station values list */}
      {/* <div className="space-y-1.5">
        {stations.map(station => {
          const value = station.measurements[activePM]
          return (
            <a
              className="flex items-center justify-between rounded-md bg-white/60 px-3 py-2 transition-colors hover:bg-white/80"
              href={`https://opensensemap.org/explore/${station.boxId}`}
              key={station.boxId}
              rel="noopener noreferrer"
              target="_blank"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {station.boxName}
                </p>
              </div>
              <div className="ml-2 flex items-center gap-2">
                {value !== undefined ? (
                  <span className="text-sm font-bold text-climate">
                    {value.toFixed(1)} µg/m³
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">–</span>
                )}
                <span className="text-xs text-gray-400">↗</span>
              </div>
            </a>
          )
        })}
      </div> */}
    </div>
  )
}
