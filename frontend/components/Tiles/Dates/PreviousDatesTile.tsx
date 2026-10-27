import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'
import SvgHeilbronn from '@/components/Icons/Heilbronn'
import { getDates } from '@/lib/api/prismaService'
import { BaseTile } from '../Base/BaseTile'
import DateCard from './DateCard'
import { getT } from '@/lib/i18n/server'

export default async function PreviousDatesTile() {
  const [dates, t] = await Promise.all([getDates(), getT()])

  const now = new Date()
  const previousDates = dates
    .filter(d => {
      const end = d.endDate ? new Date(d.endDate) : null
      const start = d.startDate ? new Date(d.startDate) : null
      // Show if end date is in the past
      if (end) {
        return end < now
      }
      if (start) {
        return start < now
      }
      return false
    })
    .sort((a, b) => {
      const aDate = new Date(a.startDate || a.endDate)
      const bDate = new Date(b.startDate || b.endDate)
      return bDate.getTime() - aDate.getTime() // Most recent first
    })

  if (previousDates.length === 0) {
    return null
  }

  return (
    <BaseTile variant="climate">
      <div className="w-full px-2.5">
        <div className="absolute right-16 top-16 hidden lg:block">
          <SvgHeilbronn className="h-[29px] w-auto flex-shrink-0 text-climate opacity-40 md:h-[50px]" />
        </div>
        <div className="flex flex-wrap items-center justify-start gap-x-4 lg:max-w-[87%]">
          <Title as="h1" className="min-w-fit text-climate" font="normal">
            {t('tiles.dates.previous')}
          </Title>
        </div>
        <Spacer />
        <div className="space-y-4">
          {previousDates.map(event => (
            <DateCard event={event} key={event.id} />
          ))}
        </div>
        <Spacer />
        <div className="text-xs">
          <Title as="h7" className="inline" font="normal" variant="primary">
            Quelle: Green City Heilbronn
          </Title>
        </div>
      </div>
    </BaseTile>
  )
}
