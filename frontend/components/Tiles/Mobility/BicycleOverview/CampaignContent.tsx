'use client'
import { ReactECharts } from '@/components/Charts/ReactECharts'
import Switch from '@/components/Inputs/Switch'
import { LineSeriesOption } from 'echarts'
import Title from '@/components/Elements/Title'
import ToggleGroup from '@/components/Inputs/ToggleGroup'
import useDevice from '@/hooks/useDevice'
import { IndicesTypes } from '../../Climate/ClimateIndices/ClimateIndicesChart'
import { useEffect, useState } from 'react'
import { getDistanceComparison, getTimeComparison } from './CompareMode'
import tailwindConfig from '@/tailwind.config'
import resolveConfig from 'tailwindcss/resolveConfig'
import { useBikeStatistics } from '@/hooks/useCampignApi'

const { theme } = resolveConfig(tailwindConfig)
const DEBUG_MODE = false
type ValuesTypes = 'distanz' | 'tracks' | 'stunden' | 'kcal'

type Campaign = {
  ZEIT: string
  Distanz: number
  Tracks: number
  Stunden: number
  Kcal: number
}

const typeMap: Record<ValuesTypes, IndicesTypes> = {
  distanz: 'tropennaechte',
  stunden: 'eistage',
  tracks: 'heisse_tage',
  kcal: 'sommertage',
}
export const getSeries = <T extends { ZEIT: string; [key: string]: any }>(
  data: T[],
  property: keyof T,
): [string, number][] => {
  return data?.map(entry => {
    const label = entry.ZEIT.slice(0, 5)
    return [label, entry[property] as number]
  })
}

function getIndices(
  CampignData: Campaign[],
): Record<ValuesTypes, { title: string; seriesOption: LineSeriesOption }> {
  return {
    distanz: {
      title: 'Distanz',
      seriesOption: {
        name: 'Distanz',
        data: getSeries<Campaign>(CampignData, 'Distanz'),
        // @ts-ignore
        color: theme?.colors?.buildings.DEFAULT || '#6060d6',
      },
    },
    stunden: {
      title: 'Stunden',
      seriesOption: {
        name: 'Stunden',
        data: getSeries<Campaign>(CampignData, 'Stunden'),
        // @ts-ignore
        color: theme?.colors?.climate.DEFAULT || '#6060d6',
      },
    },
    tracks: {
      title: 'Tracks',
      seriesOption: {
        name: 'Tracks',
        data: getSeries<Campaign>(CampignData, 'Tracks'),
        // @ts-ignore
        color: theme?.colors?.energy.DEFAULT || '#6060d6',
      },
    },
    kcal: {
      title: 'Kcal',
      seriesOption: {
        name: 'Kcal',
        data: getSeries<Campaign>(CampignData, 'Kcal'),
        // @ts-ignore
        color: theme?.colors?.mobility.DEFAULT || '#6060d6',
      },
    },
  }
}

function Toggle({
  onChange,
}: {
  onChange: (_val: 'chart' | 'compare') => void
}) {
  return (
    <ToggleGroup
      items={[
        {
          element: (
            <Title as="h5" className="2xl:w-max">
              Diagramm
            </Title>
          ),
          value: 'chart',
        },
        {
          element: (
            <Title as="h5" className="2xl:w-max">
              Alltagsvergleich
            </Title>
          ),
          value: 'compare',
        },
      ]}
      // @ts-ignore
      onChange={onChange}
      variant={'mobility'}
    />
  )
}
function CampaignIndicesToggle({
  type,
  defaultChecked,
  onChange,
  children,
  checked,
}: {
  type: IndicesTypes
  defaultChecked?: boolean
  onChange?: (_checked: boolean) => void
  children?: React.ReactNode
  checked?: boolean
  display?: boolean
}) {
  return (
    <div className="flex w-full flex-row-reverse items-center justify-between gap-2 lg:flex-row lg:justify-normal lg:gap-4">
      <Switch
        checked={checked}
        defaultChecked={defaultChecked}
        onCheckedChange={onChange}
        variant={type}
      />
      <div className="flex items-center gap-2 md:w-max md:gap-4">
        <Title as="h5" variant={type}>
          {children}
        </Title>
      </div>
    </div>
  )
}
type ComparisonEntry = {
  value: number
  description: JSX.Element
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>
  inputHours?: number
  inputDistance?: number
}

type ComparisonItemProps = {
  title: string
  comparison: ComparisonEntry
}

function ComparisonItem({ title, comparison }: ComparisonItemProps) {
  const Icon = comparison.icon

  console.log('comparison', comparison)

  return (
    <div className="p-4">
      <h3 className="text-base font-normal text-mobility xs:text-xl lg:text-4xl">
        ca.{' '}
        {title === 'Distanz' ? comparison.value + 'km' : comparison.value + 'h'}
      </h3>

      <div className="mt-3 flex gap-5">
        <div className=" ">
          <p className="text-base font-bold leading-snug xs:text-xl lg:text-4xl">
            {comparison.description}
          </p>
        </div>

        <div className="flex">
          <Icon className="h-20 w-20 items-center justify-center fill-current text-mobility lg:h-24 lg:w-24" />
        </div>
      </div>
    </div>
  )
}

export default function CampaignChart() {
  const device = useDevice()
  const [mode, setMode] = useState<'chart' | 'compare'>('chart')
  const [debugValue, setDebugValue] = useState(0)
  const [seriesVisible, setSeriesVisible] = useState<
    Record<ValuesTypes, boolean>
  >({
    distanz: true,
    stunden: false,
    tracks: false,
    kcal: false,
  })

  const bikeStats = useBikeStatistics()
  const bikeData = bikeStats?.stats || []
  const indices = getIndices(bikeData)
  const total_distance = bikeData[bikeData.length - 1]?.Distanz
  const total_time = bikeData[bikeData.length - 1]?.Stunden

  useEffect(() => {
    setSeriesVisible({
      distanz: true,
      stunden: false,
      tracks: false,
      kcal: false,
    })
  }, [mode])

  const handleToggle = (key: ValuesTypes) => {
    setSeriesVisible(prevState => {
      const newState = {
        distanz: key === 'distanz' ? !prevState.distanz : false,
        stunden: key === 'stunden' ? !prevState.stunden : false,
        tracks: key === 'tracks' ? !prevState.tracks : false,
        kcal: key === 'kcal' ? !prevState.kcal : false,
      }
      return newState
    })
  }

  console.log('indices', indices)
  const series: LineSeriesOption[] = Object.keys(indices)
    .filter(e => seriesVisible[e as ValuesTypes])
    .map(e => ({
      ...indices[e as ValuesTypes].seriesOption,
      type: 'line',
      itemStyle: {
        opacity: 0,
      },
      data: indices[e as ValuesTypes].seriesOption.data,
    }))

  const xAxisData =
    (series[0]?.data as [string, number][] | undefined)?.map(d => d[0]) ?? []
  const targetLabelCount = device === 'mobile' ? 5 : 10
  const xAxisInterval = Math.max(
    Math.ceil(xAxisData.length / targetLabelCount) - 1,
    0,
  )

  return (
    <>
      <div className="h-10"></div>
      <div className="relative bg-white">
        <div className="absolute -left-5 -top-7 flex items-center justify-end px-5 2xl:justify-between">
          <Toggle onChange={setMode} />
        </div>
        <div className="flex h-full w-full flex-col items-center gap-7 px-3 pb-5 pt-8 md:pt-10">
          <div className="h-full w-full flex-1">
            <Title as="h7" font="semibold" variant="primary">
              {seriesVisible.distanz && mode === 'chart' ? (
                <span className={device === 'mobile' ? 'pl-6' : 'pl-2 text-lg'}>
                  Km
                </span>
              ) : seriesVisible.tracks && mode === 'chart' ? (
                <span className={device === 'mobile' ? 'pl-6' : 'pl-2 text-lg'}>
                  Tracks
                </span>
              ) : seriesVisible.stunden && mode === 'chart' ? (
                <span className={device === 'mobile' ? 'pl-6' : 'pl-2 text-lg'}>
                  Stunden
                </span>
              ) : seriesVisible.kcal && mode === 'chart' ? (
                <span className={device === 'mobile' ? 'pl-6' : 'pl-2 text-lg'}>
                  Kcal
                </span>
              ) : null}
            </Title>

            {mode === 'chart' ? (
              <div className="h-[235px] w-full md:h-[440px]">
                <ReactECharts
                  option={{
                    grid: {
                      top: 20,
                      bottom: 40,
                      left: 80,
                      right: 30,
                    },
                    series: [...series],
                    xAxis: {
                      type: 'category',
                      boundaryGap: false,
                      axisLabel: {
                        fontSize: device === 'mobile' ? 12 : 20,
                        margin: 8,
                        interval: xAxisInterval,
                        hideOverlap: true,
                      },
                      data: xAxisData,
                    },
                    tooltip: {
                      show: false,
                      trigger: 'axis',
                      valueFormatter: (val: any) => {
                        return Intl.NumberFormat('de-DE').format(val.toFixed(2))
                      },
                      axisPointer: {
                        label: {
                          formatter: (params: { value: any }) => {
                            return String(params.value)
                          },
                        },
                      },
                    },
                    yAxis: {
                      type: 'value',
                      axisLabel: {
                        fontSize: device === 'mobile' ? 12 : 20,
                        formatter: (val: any) => {
                          return Intl.NumberFormat('de-DE').format(val)
                        },

                        margin: 20,
                      },
                    },
                    animation: true,
                  }}
                  settings={{
                    notMerge: true,
                  }}
                />
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {DEBUG_MODE && (
                  <input
                    className="mt-2 w-full accent-mobility"
                    max={seriesVisible.distanz ? 50000 : 720}
                    min="0"
                    onChange={e => setDebugValue(Number(e.target.value))}
                    type="range"
                    value={debugValue}
                  />
                )}
                {seriesVisible.distanz && (
                  <ComparisonItem
                    comparison={getDistanceComparison(total_distance)}
                    title="Distanz"
                  />
                )}
                {seriesVisible.stunden && (
                  <ComparisonItem
                    comparison={getTimeComparison(total_time)}
                    title="Zeit"
                  />
                )}
              </div>
            )}

            <div className="flex items-center justify-center justify-items-center">
              <div
                className={`mt-4 grid 2xl:pl-4 ${
                  mode === 'compare'
                    ? 'auto-cols-max grid-flow-col gap-6'
                    : 'grid-cols-1 gap-x-10 gap-y-4 lg:grid-cols-2'
                }`}
              >
                {(['distanz', 'stunden', 'tracks', 'kcal'] as ValuesTypes[])
                  .filter(
                    type =>
                      mode === 'chart' ||
                      type === 'distanz' ||
                      type === 'stunden',
                  )
                  .map(type => (
                    <CampaignIndicesToggle
                      checked={seriesVisible[type]}
                      key={type}
                      onChange={() => handleToggle(type)}
                      type={typeMap[type]}
                    >
                      {indices[type].title}
                    </CampaignIndicesToggle>
                  ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
