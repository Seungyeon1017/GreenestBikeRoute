import { BaseTile } from './fullWidthBucket'

export const sortTiles = (tiles: BaseTile[]) =>
  tiles.sort((a, b) => a.sort - b.sort)
