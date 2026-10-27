import { format } from 'date-fns'
import MobilityTile from '@/components/Tiles/Mobility/MobilityTile'
import CampaignChart from './CampaignContent'
import { getT } from '@/lib/i18n/server'
export default async function BicycleOverview() {
  const t = await getT()
  return (
    <MobilityTile
      dataRetrieval={format(new Date(), '01.MM.yyyy')}
      dataSource="openSenseMap"
      embedId="mobility-bicycleCampaign"
      subtitle={t('tiles.mobility.bicycleCampaign.subtitle')}
      title={t('tiles.mobility.bicycleCampaign.title')}
    >
      <CampaignChart />
    </MobilityTile>
  )
}
