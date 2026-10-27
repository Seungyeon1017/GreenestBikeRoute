import TileFactory, { TileType } from '@/utils/TileFactory'
import { notFound } from 'next/navigation'

export const revalidate = 10

type Params = Promise<{ id: TileType }>

export default async function Share({ params }: { params: Params }) {
  const { id } = await params

  if (!id) {
    return notFound()
  }

  return <TileFactory type={id} />
}
