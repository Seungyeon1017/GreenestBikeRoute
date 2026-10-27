import { getCollections } from '@/lib/api/prismaService'
import { revalidatePath } from 'next/cache'
import { NextResponse } from 'next/server'

export async function GET() {
  const collections = await getCollections('PUBLISHED')

  if (!collections || collections.length === 0) {
    return NextResponse.json({ msg: 'No data' })
  }

  const revalidatedPaths: string[] = []

  collections.forEach(({ slug }) => {
    const path = `/sammlung/${slug}`
    revalidatedPaths.push(path)
    revalidatePath(path)
  })

  return NextResponse.json({
    revalidated: true,
    now: Date.now(),
    paths: revalidatedPaths,
  })
}
