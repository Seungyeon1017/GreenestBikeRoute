import MobilityTile from '@/components/Tiles/Mobility/MobilityTile'
import TrafficFlowContent from './TrafficFlowContent'
import { getT } from '@/lib/i18n/server'

export default async function TrafficFlowTile() {
  const t = await getT()

  return (
    <MobilityTile
      dataSource="ATRAI Bikes Data Platform"
      embedId="mobility-trafficflow"
      title={t('tiles.mobility.trafficFlow.title')}
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          {t('tiles.mobility.trafficFlow.subtitle')}
        </p>
        <TrafficFlowContent />
      </div>
    </MobilityTile>
  )
}
