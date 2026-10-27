import { getPages } from '@/lib/api/prismaService'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const pages = await getPages('PUBLISHED')
    const data = pages.map(page => ({
      slug: page.slug,
      title: page.title,
    }))

    return NextResponse.json({ pages: data })
  } catch {
    return NextResponse.json(
      { pages: [], error: 'Failed to fetch pages' },
      { status: 500 },
    )
  }
}
