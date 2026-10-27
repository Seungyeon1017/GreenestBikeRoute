import MobilityTile from '@/components/Tiles/Mobility/MobilityTile'
import { getT } from '@/lib/i18n/server'
import TrafficStatsContent from './TrafficStatsContent'

export default async function TrafficStatsTile() {
  const t = await getT()

  return (
    <MobilityTile
      dataSource="ATRAI Bikes Data Platform"
      embedId="mobility-trafficstats"
      title={t('tiles.mobility.trafficStats.title')}
    >
      <TrafficStatsContent />
    </MobilityTile>
  )
}
