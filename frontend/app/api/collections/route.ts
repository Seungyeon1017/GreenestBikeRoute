import { getCollections } from '@/lib/api/prismaService'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const collections = await getCollections('PUBLISHED')
    const data = collections.map(collection => ({
      slug: collection.slug,
      title: collection.title,
    }))

    return NextResponse.json({ collections: data })
  } catch {
    return NextResponse.json(
      { collections: [], error: 'Failed to fetch collections' },
      { status: 500 },
    )
  }
}
