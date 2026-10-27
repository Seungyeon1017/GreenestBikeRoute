import Title from '@/components/Elements/Title'
import MobilityTile from '@/components/Tiles/Mobility/MobilityTile'
import getTileData from '@/lib/api/getTileData'
import { format } from 'date-fns'
import { TileSplitView } from '../../../Base/TileSplitView'
import Compare from './MapCompare'
import { getT } from '@/lib/i18n/server'

export default async function OvertakingManeuver() {
  const [data, t] = await Promise.all([getTileData('mobility-bicycleOvertaking'), getT()])
  const infoText = data?.info ?? ''

  return (
    <MobilityTile
      dataRetrieval={format(new Date(), '01.MM.yyyy')}
      dataSource="ATRAI Bikes, Unfallatlas: lizensiert unter der Datenlizenz Deutschland- Namensnennung- Version 2.0 (www.govdata.de/dl-de/by-2-0)"
      embedId="mobility-bicycleOvertaking"
      subtitle={t('tiles.mobility.overtaking.subtitle')}
      title={t('tiles.mobility.overtaking.title')}
    >
      <TileSplitView>
        <TileSplitView.Left>
          <Compare />
        </TileSplitView.Left>
        <TileSplitView.Right>
          <Title as="h5" variant={'dark'}>
            {infoText}
          </Title>
        </TileSplitView.Right>
      </TileSplitView>
    </MobilityTile>
  )
}
