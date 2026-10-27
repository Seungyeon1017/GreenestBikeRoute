import { NextResponse } from 'next/server'

const BIRDIARY_API = 'https://wiediversistmeingarten.org/api'

/**
 * GET /api/birdiary-validate?stationIds=id1,id2,...
 * Returns a random unvalidated movement from one of the given station IDs.
 */
export const GET = async (req: Request) => {
  const { searchParams } = new URL(req.url)
  const raw = searchParams.get('stationIds') ?? ''
  const stationIds = raw
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  if (stationIds.length === 0) {
    return NextResponse.json(
      { error: 'Missing stationIds parameter' },
      { status: 400 },
    )
  }

  // Pick a random station from the list, retry all if needed
  const shuffled = [...stationIds].sort(() => Math.random() - 0.5)

  for (const stationId of shuffled) {
    try {
      // /movement/{stationId} returns all movements for this station as an array
      const res = await fetch(
        `${BIRDIARY_API}/movement/${stationId}`,
        { cache: 'no-store' },
      )
      if (!res.ok) { continue }

      const movements = await res.json()
      if (!Array.isArray(movements) || movements.length === 0) { continue }

      const movement = movements[Math.floor(Math.random() * movements.length)]
      return NextResponse.json(movement)
    } catch {
      // try next station
    }
  }

  return NextResponse.json(
    { error: 'No movement found for the given stations' },
    { status: 404 },
  )
}

/**
 * POST /api/birdiary-validate
 * Body: { stationId, movId, isBird: boolean, latinName?: string, germanName?: string }
 * Forwards the validation to the WieDiVersistMeinGarten API.
 */
export const POST = async (req: Request) => {
  let body: {
    stationId: string
    movId: string
    isBird: boolean
    latinName?: string
    germanName?: string
  }

  try {
    body = await req.json()
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 })
  }

  const { stationId, movId, isBird, latinName = '', germanName = '' } = body

  if (!stationId || !movId) {
    return NextResponse.json(
      { error: 'stationId and movId are required' },
      { status: 400 },
    )
  }

  const validation = isBird
    ? { latinName: latinName || 'Unknown', germanName }
    : { latinName: 'None', germanName: '' }

  try {
    const res = await fetch(
      `${BIRDIARY_API}/validate/${stationId}/${movId}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ validation }),
      },
    )

    if (!res.ok) {
      const text = await res.text()
      return NextResponse.json(
        { error: `Upstream validation failed: ${text}` },
        { status: res.status },
      )
    }

    return NextResponse.json({ ok: true })
  } catch (err) {
    return NextResponse.json(
      { error: 'Failed to submit validation' },
      { status: 500 },
    )
  }
}
