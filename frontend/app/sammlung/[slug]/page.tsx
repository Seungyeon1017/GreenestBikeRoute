import { SuccessStoryTileProps } from '@/components/Tiles/SuccessStory'
import { SurveyTileProps } from '@/components/Tiles/Survey'
import { TileLayout } from '@/components/Tiles/TileLayout'
import {
  getCollection,
  getCollections,
  getTileData,
} from '@/lib/api/prismaService'
import { getSuccessStoryData } from '@/lib/api/getSuccessStoryData'
import { getSurveyData } from '@/lib/api/getSurveyData'
import getTilesBucket, { BaseTile } from '@/utils/fullWidthBucket'
import TileFactory, { TileType } from '@/utils/TileFactory'
import { sortTiles } from '@/utils/tileLayout'
import { notFound } from 'next/navigation'

export const revalidate = 10

// ISR
export async function generateStaticParams() {
  if (process.env.NEXT_PHASE === 'phase-production-build') {
    return []
  }

  const collections = await getCollections('PUBLISHED')

  if (!collections || collections.length === 0) {
    return [{ slug: undefined }]
  }

  return collections.map(({ slug }) => ({
    slug,
  }))
}

const getTileType = async (tileID: string) => {
  const data = await getTileData(tileID)
  return data?.tileId
}

const getTileComponent = async (tile: BaseTile) => {
  let props:
    | { surveyData?: SurveyTileProps; successStoryData?: SuccessStoryTileProps }
    | undefined
  let type: TileType

  const itemType = tile.itemType || tile.collection
  const itemId = tile.itemId || tile.item

  if (itemType === 'survey') {
    const surveyData = await getSurveyData(itemId)
    props = { surveyData }
    type = 'survey'
  } else if (itemType === 'successStory') {
    const successStoryData = await getSuccessStoryData(itemId)
    props = { successStoryData }
    type = 'successStory'
  } else {
    type = (await getTileType(itemId as string)) as TileType
  }

  return <TileFactory key={itemId} type={type} {...props} />
}

const getTileComponents = async (tiles: BaseTile[]) => {
  return Promise.all(
    tiles.map(async t => {
      return await getTileComponent(t)
    }),
  )
}

export default async function Collection(props: {
  params?: Promise<{ slug: string }>
}) {
  const params = await props.params
  if (!params?.slug) {
    return notFound()
  }

  const collection = await getCollection(params.slug)

  if (!collection) {
    return notFound()
  }

  const { tiles } = collection
  const sortedTiles = sortTiles(tiles)
  const tileBuckets = await getTilesBucket(sortedTiles)

  return <TileLayout tileBuckets={tileBuckets} />
}
