'use client'

import useTrafficFlow from '@/hooks/useTrafficFlow'
import TrafficFlowMap from './TrafficFlowMap'

export default function TrafficFlowContent() {
  const { data, error, isLoading } = useTrafficFlow()

  if (isLoading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-mobility border-t-transparent" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg bg-white">
        <p className="text-sm text-gray-500">Verkehrsflussdaten konnten nicht geladen werden.</p>
      </div>
    )
  }

  if (!data.features?.length) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg bg-white">
        <p className="text-sm text-gray-500">Keine Verkehrsflussdaten verfügbar.</p>
      </div>
    )
  }

  return <TrafficFlowMap collection={data} />
}
