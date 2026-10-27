import { getDates, getDatesPageConfig } from '@/lib/api/prismaService'
import { NextResponse } from 'next/server'

export async function GET() {
  try {
    const pageConfig = await getDatesPageConfig()
    const dates = await getDates()

    return NextResponse.json({ dates, pageConfig })
  } catch {
    return NextResponse.json(
      { dates: [], pageConfig: null, error: 'Failed to fetch dates' },
      { status: 500 },
    )
  }
}
