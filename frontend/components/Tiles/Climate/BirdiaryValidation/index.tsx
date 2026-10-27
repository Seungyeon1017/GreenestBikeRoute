import ClimateTile from '../ClimateTile'
import BirdiaryValidationTile from './BirdiaryValidationTile'
import { getT } from '@/lib/i18n/server'

const STATION_IDS = [
  '699b7f2c-3855-4273-af7f-ed61a54541f9',
  'b09ab6a3-8d47-4936-a251-e1c40bfe8d88',
]

export default async function BirdiaryValidationServerTile() {
  const t = await getT()
  return (
    <ClimateTile
      dataSource="wiediversistmeingarten.org"
      embedId={'climate-bird-validation'}
      title={t('birdiaryValidation.title')}
    >
      <BirdiaryValidationTile stationIds={STATION_IDS} />
    </ClimateTile>
  )
}
