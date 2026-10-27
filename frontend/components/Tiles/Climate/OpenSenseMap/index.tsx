import ClimateTile from '../ClimateTile'
import OpenSenseMapContent from './OpenSenseMapContent'
import { getT } from '@/lib/i18n/server'

const DEFAULT_GROUPTAG = 'GreenCityHN'

export default async function OpenSenseMapTile() {
  const t = await getT()
  return (
    <ClimateTile
      dataSource="opensensemap.org"
      embedId="climate-opensensemap"
      live
      title={t('tiles.climate.openSenseMap.title')}
    >
      <OpenSenseMapContent grouptag={DEFAULT_GROUPTAG} />
    </ClimateTile>
  )
}
