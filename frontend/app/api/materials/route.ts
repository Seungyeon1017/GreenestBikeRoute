import { getMaterialPageConfig, getMaterials } from '@/lib/api/prismaService'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const pageConfig = await getMaterialPageConfig()
    const materials = await getMaterials()

    return NextResponse.json({ materials, pageConfig })
  } catch {
    return NextResponse.json(
      { materials: [], pageConfig: null, error: 'Failed to fetch materials' },
      { status: 500 },
    )
  }
}
