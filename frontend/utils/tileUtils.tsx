// utils/tileUtils.ts
import { fetchTileType } from '@/lib/api/prismaService'
import { getSuccessStoryData } from '@/lib/api/getSuccessStoryData'
import { getSurveyData } from '@/lib/api/getSurveyData'
import TileFactory, { TileType } from '@/utils/TileFactory'
import { BaseTile } from './fullWidthBucket'

export const getTilePropsAndType = async (tile: BaseTile) => {
  const itemId = tile.itemId
  const itemType = tile.itemType

  if (itemType === 'survey' && itemId) {
    const surveyData = await getSurveyData(itemId)
    return { type: 'survey' as TileType, props: { surveyData } }
  }

  if (itemType === 'successStory' && itemId) {
    const successStoryData = await getSuccessStoryData(itemId)
    return { type: 'successStory' as TileType, props: { successStoryData } }
  }

  if (itemType === 'dates-upcoming') {
    return { type: 'dates-upcoming' as TileType, props: {} }
  }

  if (itemType === 'dates-previous') {
    return { type: 'dates-previous' as TileType, props: {} }
  }

  if (itemType === 'material') {
    return { type: 'material' as TileType, props: {} }
  }

  let type = undefined
  if (itemId) {
    const tileData = await fetchTileType(itemId)
    type = tileData.tileId as TileType | undefined
    if (!tileData) {
      throw new Error(`Tile not found: ${itemId}`)
    }
  }
  return { type, props: {} }
}

export const renderTileComponent = async (tile: BaseTile) => {
  const { type, props } = await getTilePropsAndType(tile)
  const itemId = tile.itemId
  if (type) {
    return <TileFactory key={itemId} type={type} {...props} />
  }
}

export const renderTileComponents = async (tiles: BaseTile[]) => {
  return Promise.all(tiles.map(tile => renderTileComponent(tile)))
}
