/**
 * Whether the sun is up in Heilbronn at a departure time, the same way the
 * backend decides between shade (by day) and lighting (after dark):
 * routing/shadow.py sun_position() and routing/route.py sky().
 */

/** Heilbronn, as routing/shadow.py LAT0 / LON0. */
const LAT = 49.14
const LON = 9.22
/** Sunrise and sunset: the top of the sun on the horizon, refraction included. */
const SUNSET_ALTITUDE = -0.833
const TIME_ZONE = 'Europe/Berlin'

const rad = (deg: number) => (deg * Math.PI) / 180
const deg = (r: number) => (r * 180) / Math.PI

/** Sun altitude in degrees at `when` (NOAA solar equations, ~0.1°). */
function sunAltitude(when: Date): number {
  const jd = when.getTime() / 86_400_000 + 2440587.5
  const jc = (jd - 2451545) / 36525
  const l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
  const m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
  const e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
  const mr = rad(m)
  const c =
    Math.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) +
    Math.sin(2 * mr) * (0.019993 - 0.000101 * jc) +
    Math.sin(3 * mr) * 0.000289
  const omega = 125.04 - 1934.136 * jc
  const appLong = l0 + c - 0.00569 - 0.00478 * Math.sin(rad(omega))
  const eps0 =
    23 +
    (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
  const eps = rad(eps0 + 0.00256 * Math.cos(rad(omega)))
  const decl = Math.asin(Math.sin(eps) * Math.sin(rad(appLong)))
  const y = Math.tan(eps / 2) ** 2
  const l0r = rad(l0)
  const eqTime =
    4 *
    deg(
      y * Math.sin(2 * l0r) -
        2 * e * Math.sin(mr) +
        4 * e * y * Math.sin(mr) * Math.cos(2 * l0r) -
        0.5 * y * y * Math.sin(4 * l0r) -
        1.25 * e * e * Math.sin(2 * mr),
    )
  const minutes =
    when.getUTCHours() * 60 + when.getUTCMinutes() + when.getUTCSeconds() / 60
  const hourAngle = rad((minutes + eqTime + 4 * LON) / 4 - 180)
  const latr = rad(LAT)
  const cosZen =
    Math.sin(latr) * Math.sin(decl) +
    Math.cos(latr) * Math.cos(decl) * Math.cos(hourAngle)
  return 90 - deg(Math.acos(Math.max(-1, Math.min(1, cosZen))))
}

/**
 * "YYYY-MM-DDTHH:mm" in Heilbronn time (whatever the browser's time zone) → the instant.
 * Reads it as UTC first, then corrects by Berlin's offset at that moment (CET or CEST).
 */
function heilbronnTime(local: string): Date | null {
  const asUtc = new Date(`${local}:00Z`)
  if (Number.isNaN(asUtc.getTime())) {
    return null
  }
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: TIME_ZONE,
      hourCycle: 'h23',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
      .formatToParts(asUtc)
      .map(p => [p.type, p.value]),
  )
  const berlinAsUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
  )
  return new Date(asUtc.getTime() - (berlinAsUtc - asUtc.getTime()))
}

/**
 * True if the sun is up at the departure (shade counts), false after sunset or
 * before sunrise on that date (lighting counts), null without a valid time.
 */
export function isSunUp(departTime: string): boolean | null {
  const when = departTime ? heilbronnTime(departTime) : null
  return when ? sunAltitude(when) >= SUNSET_ALTITUDE : null
}
