import { TileType } from '@/utils/TileFactory'
import { getTileData as getTileDataFromPrisma } from './prismaService'

export default async function getTileData(id: TileType) {
  const data = await getTileDataFromPrisma(id)
  return data
}
