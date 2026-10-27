import BirdTile from '@/components/Tiles/Climate/Bird'
import BirdiaryStationsTile from '@/components/Tiles/Climate/BirdiaryStations'
import BirdiaryValidationTile from '@/components/Tiles/Climate/BirdiaryValidation'
import ClimateIndicesTile from '@/components/Tiles/Climate/ClimateIndices'
import ClimateDevelopmentTile from '@/components/Tiles/Climate/Devlopment'
import OpenSenseMapTile from '@/components/Tiles/Climate/OpenSenseMap'
import PMTile from '@/components/Tiles/Climate/PM'
import WeatherTile from '@/components/Tiles/Climate/WeatherTile'
import PreviousDatesTile from '@/components/Tiles/Dates/PreviousDatesTile'
import UpcomingDatesTile from '@/components/Tiles/Dates/UpcomingDatesTile'
import MaterialTile from '@/components/Tiles/Material/MaterialTile'
import BicycleChartTile from '@/components/Tiles/Mobility/Bicycle/BicycleChartTile'
import OvertakingManeuver from '@/components/Tiles/Mobility/Bicycle/OvertakingManeuver'
import BicycleOverview from '@/components/Tiles/Mobility/BicycleOverview'
import TrafficFlowTile from '@/components/Tiles/Mobility/TrafficFlowTile'
import TrafficStatsTile from '@/components/Tiles/Mobility/TrafficStatsTile'
import SuccessStoryTile, {
  SuccessStoryTileProps,
} from '@/components/Tiles/SuccessStory'
import SurveyTile, { SurveyTileProps } from '@/components/Tiles/Survey'
import { getSuccessStoryData } from '@/lib/api/getSuccessStoryData'
import { getSurveyData } from '@/lib/api/getSurveyData'
import {
  BuildingsTypes,
  ClimateTypes,
  EnergyTypes,
  MobilityTypes,
  TileTypePrefix,
} from '@/types/tile'

type TileTypeSuffix =
  | ClimateTypes
  | MobilityTypes
  | BuildingsTypes
  | EnergyTypes
  | string

type SuccessStoryTileType = 'successStory'
type SurveyTileType = 'survey'
type DatesTileType = 'dates-upcoming' | 'dates-previous'
type MaterialTileType = 'material' | 'climate-material'
type BirdTileType = 'climate-bird'
type BirdiaryStationsTileType = 'climate-bird-stations'
type BirdiaryValidationTileType = 'climate-bird-validation'
type OpenSenseMapTileType = 'climate-opensensemap'
type PMTileType = 'climate-pm'

export type TileType =
  | SuccessStoryTileType
  | SurveyTileType
  | DatesTileType
  | MaterialTileType
  | BirdTileType
  | BirdiaryStationsTileType
  | BirdiaryValidationTileType
  | OpenSenseMapTileType
  | PMTileType
  | `${TileTypePrefix}-${TileTypeSuffix}`

interface TileFactoryProps {
  type: TileType
  successStoryData?: SuccessStoryTileProps
  surveyData?: SurveyTileProps
}

/**
 * The TileFactory is a helper function to create tiles dynamically.
 *
 * @param param TileFactoryProps
 * @returns Tile
 */
export default async function TileFactory({
  type,
  ...props
}: TileFactoryProps) {
  if (type?.startsWith('survey')) {
    const [_, id] = type.split('survey-')
    if (props.surveyData) {
      return <SurveyTile {...props.surveyData} />
    }
    const data = await getSurveyData(id)
    if (!data) {
      return null
    }
    return <SurveyTile {...data} />
  }

  if (type?.startsWith('successStory')) {
    const [_, id] = type.split('successStory-')
    if (props.successStoryData) {
      return <SuccessStoryTile {...props.successStoryData} />
    }
    const data = await getSuccessStoryData(id)
    if (!data) {
      return null
    }
    return <SuccessStoryTile {...data} />
  }

  switch (type) {
    // ---- WEATHER ----
    case 'climate-weather':
      return <WeatherTile />
    case 'climate-indices':
      return <ClimateIndicesTile />
    case 'climate-development':
      return <ClimateDevelopmentTile />
    case 'climate-bird':
      return <BirdTile />
    case 'climate-bird-stations':
      return <BirdiaryStationsTile />
    case 'climate-bird-validation':
      return <BirdiaryValidationTile />
    case 'climate-opensensemap':
      return <OpenSenseMapTile />
    case 'climate-pm':
      return <PMTile />

    // ---- DATES ----
    case 'dates-upcoming':
      return <UpcomingDatesTile />
    case 'dates-previous':
      return <PreviousDatesTile />

    // ---- MATERIAL ----
    case 'material':
    case 'climate-material':
      return <MaterialTile />

    // ---- MOBILITY ----
    case 'mobility-bicycle':
      return <BicycleChartTile />
    case 'mobility-trafficflow':
      return <TrafficFlowTile />
    case 'mobility-trafficstats':
      return <TrafficStatsTile />
    case 'mobility-bicycleCampaign':
      return <BicycleOverview />
    case 'mobility-bicycleOvertaking':
      return <OvertakingManeuver />

    default:
      return null
  }
}
