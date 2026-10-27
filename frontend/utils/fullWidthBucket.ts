import { fetchTileType, getTileData } from '@/lib/api/prismaService'

// super complex and probably overkill function to seperate fill width from normal tiles
export type BaseTile = {
  id: string
  collections_id?: string
  item: string
  itemId?: string
  tileId?: string
  itemType?: string
  collection: string
  sort: number
}

export type TilesBucket = {
  tiles: BaseTile[]
  isFullWidth: boolean
}

// check if a tile should be displayed full width
const isFullWidth = async (tile: BaseTile) => {
  // Handle new Prisma structure
  const itemType = tile.itemType || tile.collection

  if (itemType === 'successStory') {
    return true
  }

  if (itemType === 'survey') {
    return false
  }

  if (itemType === 'dates-upcoming' || itemType === 'dates-previous') {
    return true
  }

  if (itemType === 'material') {
    return true
  }

  // For regular tiles, check fullWidth property
  // First try by tileId string (e.g. 'climate-material')
  if (tile.tileId) {
    const data = await getTileData(tile.tileId)
    return data?.fullWidth === true
  }

  // Then try by item UUID (e.g. from PageTile.itemId)
  if (tile.itemId) {
    try {
      const data = await fetchTileType(tile.itemId)
      return data?.fullWidth === true
    } catch {
      return false
    }
  }

  return false
}

/**
 * Some tiles must be displayed full width, while others are displayed as pairs in columns.
 * This function gets a list of tiles and places them into buckets
 * Each bucket has a list of tiles and the property whether the included
 * tile(s) should be rendered as full width tiles. A full width tile is always alone in its
 * bucket 😞
 *
 * @example
 * ```
   // this will be the full width tile (as defined in the directus CMS)
   const tileA = {
    id: "A",
    collections_id: "ABC"
    ...
   }
   const tileB = {
    id: "B",
    collections_id: "ABC"
    ...
   }
   const tileC = {
    id: "C",
    collections_id: "ABC"
    ...
   }

   const buckets = await getTilesBucket([tileA, tileB, tileC])

   [
    {
        tiles: [{id: "A", collections_id: "ABC" ...}],
        isFullWidth: true
    }
    {
        tiles: [{id: "B", collections_id: "ABC" ...}, {id: "C", collections_id: "ABC" ...}],
        isFullWidth: false
    }
   ]
   ```
 *
 * @param tiles all tiles that should be sorted into buckets
 * @returns a list of buckets
 */
const getTilesBucket = async (tiles: BaseTile[]) => {
  let bucketIndex = 0
  const fullWidthIndex = await tiles.reduce(async function (aP, e) {
    const a = await aP
    if (!a[bucketIndex]) {
      a[bucketIndex] = {
        tiles: [],
        isFullWidth: false,
      }
    }
    if (!(await isFullWidth(e))) {
      a[bucketIndex].tiles.push(e)
    } else {
      bucketIndex++
      a[bucketIndex] = {
        tiles: [],
        isFullWidth: true,
      }
      a[bucketIndex].tiles.push(e)
      bucketIndex++
    }
    return a
  }, Promise.resolve<TilesBucket[]>([]))

  return fullWidthIndex
}

export default getTilesBucket
