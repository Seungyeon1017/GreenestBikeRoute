'use client'

import Slider from '@/components/Inputs/Slider'
import { format, subDays } from 'date-fns'
import { useState } from 'react'
import BicycleRow from './BicycleRow'
import LoadingRow from './LoadingRow'
import { useEcoCounter } from '@/hooks/useEcoCounterApi'
import Title from '@/components/Elements/Title'

export default function BicycleChartContent() {
  const lastDays = new Array(7)
    .fill(undefined)
    .map((e, i) => subDays(new Date(), i + 1))
    .reverse()

  const [date, setDate] = useState<Date>(lastDays[lastDays.length - 1])

  const { data, min, max, stationCount, loading } = useEcoCounter(date)

  const year = new Date().getFullYear()

  return (
    <>
      <div className="rounded bg-white px-4 py-2">
        {loading &&
          new Array(stationCount)
            .fill(undefined)
            .map((_e, i) => <LoadingRow key={i} />)}
        {data &&
          data.map(e => (
            <BicycleRow
              count={e.weeklyCount}
              key={e.id}
              max={max}
              min={min}
              name={e.name}
              yearlyCount={e.yearlyCount}
            />
          ))}
        <div className="mt-8 flex w-full">
          <Title as="h8" variant={'energy'}>
            * Total {year}
          </Title>
        </div>
      </div>
      {lastDays.length > 0 && (
        <Slider
          defaultValue={[lastDays.length - 1]}
          firstValueMobile={lastDays.length - 1}
          labels={lastDays.map(d => format(d, 'dd.MM.'))}
          max={lastDays.length - 1}
          min={0}
          onValueChange={([e]) => {
            setDate(lastDays[e])
          }}
          variant={'mobility'}
        />
      )}
    </>
  )
}
