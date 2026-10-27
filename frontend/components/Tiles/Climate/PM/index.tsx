import ClimateTile from '../ClimateTile'
import PMContent from './PMContent'
import { getT } from '@/lib/i18n/server'

const DEFAULT_GROUPTAG = 'GreenCityHN'

export default async function PMTile() {
  const t = await getT()
  return (
    <ClimateTile
      dataSource="opensensemap.org"
      embedId="climate-pm"
      live
      title={t('tiles.climate.pm.title')}
    >
      <PMContent grouptag={DEFAULT_GROUPTAG} />
    </ClimateTile>
  )
}
