import ClimateTile from '../ClimateTile'
import BirdiaryValidationStationsMap from '../BirdiaryValidation/BirdiaryValidationStationsMap'
import { getT } from '@/lib/i18n/server'

const STATION_IDS_FOR_MAP = [
  '699b7f2c-3855-4273-af7f-ed61a54541f9',
  'b09ab6a3-8d47-4936-a251-e1c40bfe8d88',
  '1f4f6586-67c8-4dd2-aa5d-2aa4c0dba94d',
  'aec5edea-0a4f-4ab7-b0b1-77eb98552a0d',
  'f5ad4530-e3b0-43cf-8b00-c6a9d5e4e4e2',
  '1292a46b-b8ce-449e-b50b-112f0c864e50',
  '785d6318-433f-42bc-9328-8dd02d347fb8',
]

export default async function BirdiaryStationsTile() {
  const t = await getT()

  return (
    <ClimateTile
      dataSource="wiediversistmeingarten.org"
      embedId="climate-bird-stations"
      title={t('tiles.climate.birdStations.title')}
    >
      <BirdiaryValidationStationsMap stationIds={STATION_IDS_FOR_MAP} />
    </ClimateTile>
  )
}
