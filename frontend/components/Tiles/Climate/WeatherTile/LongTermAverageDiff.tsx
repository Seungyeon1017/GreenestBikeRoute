import AnimatedNumber from '@/components/Elements/Animated/AnimatedNumber'
import Title from '@/components/Elements/Title'
import { format } from 'date-fns'
import { de } from 'date-fns/locale'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

export default function LongTermAverageDiff() {
  const [difference, setDifference] = useState<number>()
  const { t } = useTranslation()

  async function getData() {
    try {
      const request = await fetch(
        'https://long-term-average.klimadashboard-ms.reedu.de/',
      )
      const data = await request.json()
      setDifference(data.value)
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error("Couldn't fetch long term average difference", error)
    }
  }

  useEffect(() => {
    getData()
  }, [])

  if (!difference) {
    return null
  }

  return (
    <Title as={'h4'}>
      <span className="text-climate">
        <AnimatedNumber decimals={2}>{Math.abs(difference)}</AnimatedNumber>{' '}
        {t(difference > 0 ? 'weatherTile.degreeWarmer' : 'weatherTile.degreeColder')}
      </span>{' '}
      {t('weatherTile.isThe')}{' '}
      <span className="text-climate">
        {format(new Date(), 'LLLL', { locale: de })}
      </span>{' '}
      {t('weatherTile.comparisonSuffix')}
    </Title>
  )
}
