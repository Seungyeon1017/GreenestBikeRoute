'use client'

import { ReactECharts } from '@/components/Charts/ReactECharts'
import useTrafficStats from '@/hooks/useTrafficStats'
import type { WeeklyStatEntry } from '@/hooks/useTrafficStats'
import { format, parseISO } from 'date-fns'
import { de } from 'date-fns/locale'
import { useState } from 'react'

type MetricKey = 'trip_count' | 'total_distance_m' | 'average_speed_kmh' | 'total_kcal'

type MetricConfig = {
  key: MetricKey
  label: string
  unit: string
  color: string
  format: (_v: number) => string
}

const METRICS: MetricConfig[] = [
  {
    key: 'trip_count',
    label: 'Fahrten',
    unit: '',
    color: '#34c17b',
    format: v => v.toFixed(0),
  },
  {
    key: 'total_distance_m',
    label: 'Distanz',
    unit: 'km',
    color: '#0c4da2',
    format: v => (v / 1000).toFixed(1),
  },
  {
    key: 'average_speed_kmh',
    label: 'Ø Geschw.',
    unit: 'km/h',
    color: '#f97316',
    format: v => v.toFixed(1),
  },
  {
    key: 'total_kcal',
    label: 'Kalorien',
    unit: 'kcal',
    color: '#a855f7',
    format: v => v.toFixed(0),
  },
]

function formatWeek(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'dd. MMM', { locale: de })
  } catch {
    return dateStr
  }
}

function getDisplayValue(entry: WeeklyStatEntry, key: MetricKey): number {
  if (key === 'total_distance_m') {
    return entry.total_distance_m / 1000
  }
  return entry[key]
}

function formatTooltipNumber(value: unknown): string {
  const numericValue = typeof value === 'number' ? value : Number(value)

  if (!Number.isFinite(numericValue)) {
    return String(value)
  }

  return numericValue.toLocaleString('de-DE', {
    maximumFractionDigits: 2,
  })
}

export default function TrafficStatsContent() {
  const { data, isLoading, error } = useTrafficStats()
  const [activeMetric, setActiveMetric] = useState<MetricKey>('trip_count')

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-mobility border-t-transparent" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex h-40 items-center justify-center">
        <p className="text-sm text-gray-500">Statistikdaten konnten nicht geladen werden.</p>
      </div>
    )
  }

  const { latest_stats, weekly_stats } = data
  const metric = METRICS.find(m => m.key === activeMetric)!
  const weeks = weekly_stats.slice(-20) // show last 20 weeks

  const chartLabels = weeks.map(w => formatWeek(w.week))
  const chartValues = weeks.map(w => getDisplayValue(w, activeMetric))

  const chartOption = {
    grid: { top: 20, right: 8, bottom: 40, left: 50 },
    xAxis: {
      type: 'category' as const,
      data: chartLabels,
      axisLabel: {
        rotate: 35,
        fontSize: 11,
        color: '#6b7280',
      },
      axisLine: { lineStyle: { color: '#e5e7eb' } },
    },
    yAxis: {
      type: 'value' as const,
      axisLabel: {
        formatter: (v: number) =>
          metric.unit ? `${v} ${metric.unit}` : `${v}`,
        fontSize: 11,
        color: '#6b7280',
      },
      splitLine: { lineStyle: { color: '#f3f4f6' } },
    },
    tooltip: {
      trigger: 'axis' as const,
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const tooltipValue = formatTooltipNumber(p.value)
        return `<div style="padding:4px 8px">
          <strong>${p.name}</strong><br/>
          ${metric.label}: <strong>${tooltipValue} ${metric.unit}</strong>
        </div>`
      },
    },
    series: [
      {
        type: 'bar' as const,
        data: chartValues,
        itemStyle: { color: metric.color, borderRadius: [3, 3, 0, 0] },
        emphasis: { itemStyle: { opacity: 0.8 } },
      },
    ],
  }

  const totalDistance = (latest_stats.total_distance_m / 1000).toFixed(1)
  const avgSpeed = latest_stats.average_speed_kmh.toFixed(1)
  const totalKcal = Math.round(latest_stats.total_kcal).toLocaleString('de-DE')

  return (
    <div className="space-y-5">
      {/* Summary boxes */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-lg bg-white/70 p-3 text-center">
          <p className="text-2xl font-bold text-mobility">{latest_stats.trip_count}</p>
          <p className="text-xs text-gray-500">Fahrten gesamt</p>
        </div>
        <div className="rounded-lg bg-white/70 p-3 text-center">
          <p className="text-2xl font-bold text-mobility">{totalDistance} km</p>
          <p className="text-xs text-gray-500">Gesamtdistanz</p>
        </div>
        <div className="rounded-lg bg-white/70 p-3 text-center">
          <p className="text-2xl font-bold text-mobility">{avgSpeed} km/h</p>
          <p className="text-xs text-gray-500">Ø Geschwindigkeit</p>
        </div>
        <div className="rounded-lg bg-white/70 p-3 text-center">
          <p className="text-2xl font-bold text-mobility">{totalKcal}</p>
          <p className="text-xs text-gray-500">Kalorien verbrannt</p>
        </div>
      </div>

      {/* Metric toggle */}
      <div className="flex flex-wrap gap-2">
        {METRICS.map(m => (
          <button
            className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
              activeMetric === m.key
                ? 'text-white'
                : 'bg-white/60 text-gray-600 hover:bg-white/80'
            }`}
            key={m.key}
            onClick={() => setActiveMetric(m.key)}
            style={activeMetric === m.key ? { backgroundColor: m.color } : {}}
            type="button"
          >
            {m.label}
            {m.unit ? ` (${m.unit})` : ''}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-64 w-full rounded-lg bg-white/70 p-3 md:h-80">
        <ReactECharts
          option={chartOption}
          style={{ height: '100%', width: '100%' }}
        />
      </div>

      {/* Per-week detail for active metric */}
      <div className="space-y-1.5">
        {weeks
          .slice()
          .reverse()
          .slice(0, 5)
          .map(entry => {
            const max = Math.max(...weeks.map(w => getDisplayValue(w, activeMetric)), 1)
            const val = getDisplayValue(entry, activeMetric)
            const barWidth = (val / max) * 100
            const displayVal = metric.format(entry[activeMetric])

            return (
              <div className="flex items-center gap-2" key={entry.week}>
                <span className="w-16 shrink-0 text-xs text-gray-500">
                  {formatWeek(entry.week)}
                </span>
                <div className="relative h-5 flex-1 overflow-hidden rounded-full bg-white/60">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full transition-all"
                    style={{ width: `${barWidth}%`, backgroundColor: metric.color + 'aa' }}
                  />
                  <span className="relative z-10 flex h-full items-center px-2 text-xs font-medium text-gray-700">
                    {displayVal} {metric.unit}
                  </span>
                </div>
              </div>
            )
          })}
      </div>
    </div>
  )
}
