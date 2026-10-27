import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'
import MobilityTile from '@/components/Tiles/Mobility/MobilityTile'
import BicycleChartContent from './BicycleChartContent'
import getTileData from '@/lib/api/getTileData'
import { getT } from '@/lib/i18n/server'

export default async function BicycleChartTile() {
  const [data, t] = await Promise.all([getTileData('mobility-bicycle'), getT()])
  const infoText = data?.info ?? ''

  return (
    <MobilityTile
      dataSource="Eco-Counter, NeoSens"
      embedId="mobility-bicycle"
      live
      subtitle={t('tiles.mobility.bicycle.subtitle')}
      title={t('tiles.mobility.bicycle.title')}
    >
      <>
        <BicycleChartContent />
        <Spacer size={'lg'} />
        <Title as="h5">{infoText}</Title>
      </>
    </MobilityTile>
  )
}
