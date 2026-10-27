import ClimateTile from '../ClimateTile'
import BirdTileContent from './BirdTileContent'
import { getT } from '@/lib/i18n/server'

const DEFAULT_STATION_ID = '699b7f2c-3855-4273-af7f-ed61a54541f9'

export default async function BirdTile() {
  const t = await getT()
  return (
    <ClimateTile
      dataSource="wiediversistmeingarten.org"
      embedId={'climate-bird'}
      live
      title={t('tiles.climate.bird.title')}
    >
      <BirdTileContent stationId={DEFAULT_STATION_ID} />
    </ClimateTile>
  )
}
