import ClimateTile from '../ClimateTile'
import WeatherTileContent from './WeatherTileContent'
import { getT } from '@/lib/i18n/server'

export default async function WeatherTile() {
  const t = await getT()
  return (
    <ClimateTile
      dataSource="Deutscher Wetterdienst"
      embedId={'climate-weather'}
      live
      title={t('tiles.climate.weather.title')}
    >
      <WeatherTileContent />
    </ClimateTile>
  )
}
