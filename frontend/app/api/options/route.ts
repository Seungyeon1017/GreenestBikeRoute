import { NextResponse } from 'next/server'
import { prisma } from '@/lib/prisma'

export async function GET() {
  try {
    const options = await prisma.appOptions.findFirst()
    const languages = options?.languages ?? []
    return NextResponse.json({ languages })
  } catch {
    return NextResponse.json(
      { languages: [], error: 'Failed to fetch languages' },
      { status: 500 },
    )
  }
}
