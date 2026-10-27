import AnimatedNumber from '@/components/Elements/Animated/AnimatedNumber'
import Title from '@/components/Elements/Title'
import BicycleProgress from './BicycleProgress'

type BicycleRowProps = {
  name: string
  count: number
  min: number
  max: number
  yearlyCount: number
}

function mapBetween(
  currentNum: number,
  min: number,
  max: number,
  minAllowed = 0,
  maxAllowed = 100,
) {
  return (
    ((maxAllowed - minAllowed) * (currentNum - min)) / (max - min) + minAllowed
  )
}

export default function BicycleRow({
  name,
  count,
  min,
  max,
  yearlyCount,
}: BicycleRowProps) {
  const progress = mapBetween(count, min * 0.9, max * 1.1)

  return (
    <div className="my-4 flex w-full items-end">
      <div className="w-28 flex-none md:w-40">
        <Title as={'h5'} variant={'primary'}>
          {name}
        </Title>
        <Title as={'h3'} variant={'mobility'}>
          <AnimatedNumber>{count}</AnimatedNumber>
        </Title>
        <Title as={'h4'} className="flex items-start" variant={'energy'}>
          <AnimatedNumber>{yearlyCount}</AnimatedNumber>
          {/* hochgestellt */}
          <span className="text-md"> * </span>
        </Title>
      </div>
      <div className="mb-2 flex-1 md:mb-4">
        <BicycleProgress progress={progress} />
      </div>
    </div>
  )
}
