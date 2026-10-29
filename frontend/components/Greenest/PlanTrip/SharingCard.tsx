'use client'

import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import type {
  SharingTrip,
  SharingVehicleChoice,
  VehicleCollection,
  VehicleProperties,
  ZoneCollection,
} from '@/types/greenest'
import { ROUTE_COLORS } from './RouteComparison'

/** Teal e-bike, pink e-scooter: apart from the route greens and the danger/air colours. */
export const VEHICLE_COLORS = { bike: '#00838f', scooter: '#d81b60' } as const
/** Walks of the rented-vehicle trip. */
export const WALK_COLOR = '#37474f'
/** Below this battery a vehicle is drawn faded. */
export const LOW_BATTERY_PCT = 20

/** Only links that open the provider's page or app, never `javascript:` or the like. */
export function safeRentUrl(url: string | null): string | null {
  return url?.startsWith('https://') ? url : null
}

/** "€1.00 to unlock + €0.44/min" → the price in € of riding `seconds` (started minutes count), or null. */
export function priceFor(price: string | null, seconds: number): number | null {
  const m = /€([\d.]+) to unlock \+ €([\d.]+)\/min/.exec(price ?? '')
  return m ? Number(m[1]) + Number(m[2]) * Math.ceil(seconds / 60) : null
}

/** "€1.00 to unlock + €0.44/min" in the page's language and number format; other prices as given. */
export function localPrice(
  price: string,
  t: (_key: string, _values?: Record<string, unknown>) => string,
  language: string,
): string {
  const m = /€([\d.]+) to unlock \+ €([\d.]+)\/min/.exec(price)
  if (!m) {
    return price
  }
  const euro = (value: string) =>
    Number(value).toLocaleString(language, {
      style: 'currency',
      currency: 'EUR',
    })
  return t('greenest.planTrip.sharing.price', {
    unlock: euro(m[1]),
    perMin: euro(m[2]),
  })
}

const minutes = (seconds: number) => Math.max(1, Math.round(seconds / 60))
const km = (metres: number) => (metres / 1000).toFixed(1)

function formatTime(iso: string, language: string) {
  return new Date(iso).toLocaleTimeString(language, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

type SharingCardProps = {
  hasStart: boolean
  hasRoute: boolean
  // Shared vehicles on the map.
  show: boolean
  onShowChange: (_show: boolean) => void
  vehicle: SharingVehicleChoice
  onVehicleChange: (_vehicle: SharingVehicleChoice) => void
  vehicles: VehicleCollection | null
  zones: ZoneCollection | null
  error: string | null
  // The trip with a rented vehicle.
  tripOn: boolean
  onTripOnChange: (_on: boolean) => void
  tripVehicle: SharingVehicleChoice
  onTripVehicleChange: (_vehicle: SharingVehicleChoice) => void
  trip: SharingTrip | null
  /** The same trip without the rider's settings, to compare with. */
  plainTrip: SharingTrip | null
  tripError: string | null
  tripLoading: boolean
}

const SELECT =
  'rounded-lg border border-leaf-sand bg-white px-2 py-1 text-sm text-leaf-ink disabled:opacity-40'

function Dot({ color, faded = false }: { color: string; faded?: boolean }) {
  return (
    <span
      aria-hidden
      className="inline-block h-2.5 w-2.5 rounded-full border border-white"
      style={{ background: color, opacity: faded ? 0.35 : 1 }}
    />
  )
}

/** Shared Dott e-bikes and e-scooters: where they stand now, and a trip with one (walk, ride, walk). */
export default function SharingCard(props: SharingCardProps) {
  const { t, i18n } = useTranslation()
  const { show, vehicles, zones, error, tripOn, trip, tripError } = props
  const s = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.sharing.${key}`, values)
  const name = (v: VehicleProperties['vehicle']) => s(`vehicle.${v}`)

  const count = (kind: 'bike' | 'scooter') =>
    vehicles?.features.filter(f => f.properties.vehicle === kind).length ?? 0
  const nearest = props.hasStart ? (vehicles?.features.slice(0, 3) ?? []) : []

  return (
    <Card>
      <div className="flex flex-col gap-4">
        <CardTitle>{s('title')}</CardTitle>

        {/* Rent one for this trip: the walk–ride–walk plan. */}
        <section className="flex flex-col gap-2">
          <label className="flex cursor-pointer items-start gap-2 text-sm text-leaf-ink/80">
            <input
              checked={tripOn}
              className="mt-0.5 h-4 w-4 accent-leaf-forest"
              onChange={e => props.onTripOnChange(e.target.checked)}
              type="checkbox"
            />
            <span>{s('tripToggle')}</span>
          </label>
          <select
            aria-label={s('tripVehicleLabel')}
            className={SELECT}
            disabled={!tripOn}
            onChange={e =>
              props.onTripVehicleChange(e.target.value as SharingVehicleChoice)
            }
            value={props.tripVehicle}
          >
            <option value="all">{s('choice.quickest')}</option>
            <option value="bike">{s('vehicle.bike')}</option>
            <option value="scooter">{s('vehicle.scooter')}</option>
          </select>

          {tripOn && !props.hasRoute && (
            <p className="text-xs text-leaf-muted">{s('needRoute')}</p>
          )}
          {tripOn && props.tripLoading && (
            <p className="text-xs text-leaf-muted" role="status">
              {s('tripLoading')}
            </p>
          )}
          {tripOn && tripError && (
            <p className="text-xs text-red-700" role="alert">
              {tripError}
            </p>
          )}
          {tripOn && trip && <TripSteps name={name} s={s} trip={trip} />}
          {tripOn && trip && props.plainTrip && (
            <TripComparison plain={props.plainTrip} trip={trip} />
          )}
        </section>

        <hr className="border-leaf-sand/70" />

        {/* Every free vehicle on the map. */}
        <section className="flex flex-col gap-2">
          <label className="flex cursor-pointer items-start gap-2 text-sm text-leaf-ink/80">
            <input
              checked={show}
              className="mt-0.5 h-4 w-4 accent-leaf-forest"
              onChange={e => props.onShowChange(e.target.checked)}
              type="checkbox"
            />
            <span>{s('showToggle')}</span>
          </label>
          <select
            aria-label={s('vehicleLabel')}
            className={SELECT}
            disabled={!show}
            onChange={e =>
              props.onVehicleChange(e.target.value as SharingVehicleChoice)
            }
            value={props.vehicle}
          >
            <option value="all">{s('choice.both')}</option>
            <option value="bike">{s('vehicle.bike')}</option>
            <option value="scooter">{s('vehicle.scooter')}</option>
          </select>

          {show && error && (
            <p className="text-xs text-red-700" role="alert">
              {error}
            </p>
          )}

          {show && vehicles && (
            <>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-leaf-muted">
                <span className="flex items-center gap-1">
                  <Dot color={VEHICLE_COLORS.bike} /> {s('vehicle.bike')}
                </span>
                <span className="flex items-center gap-1">
                  <Dot color={VEHICLE_COLORS.scooter} /> {s('vehicle.scooter')}
                </span>
                {zones && (
                  <span className="flex items-center gap-1">
                    <span
                      aria-hidden
                      className="inline-block h-2.5 w-2.5 rounded-full border-2 border-[#37474f] bg-white"
                    />
                    {s('zone')}
                  </span>
                )}
                <span>{s('lowBattery', { pct: LOW_BATTERY_PCT })}</span>
              </div>

              <p className="text-sm text-leaf-ink/80">
                {s(`summary.${props.vehicle}`, {
                  bikes: count('bike'),
                  scooters: count('scooter'),
                })}
              </p>

              {nearest.length > 0 ? (
                <ul className="flex flex-col gap-2">
                  {nearest.map(f => {
                    const p = f.properties
                    const url = safeRentUrl(p.rent_url)
                    return (
                      <li
                        className="flex flex-col gap-0.5 rounded-xl border border-leaf-sand/70 px-3 py-2 text-xs text-leaf-ink/80"
                        key={p.vehicle_id}
                      >
                        <span className="flex items-center gap-1.5 font-medium text-leaf-ink">
                          <Dot color={VEHICLE_COLORS[p.vehicle]} />
                          {p.provider} {name(p.vehicle)}
                          {p.distance_m != null && (
                            <span className="ml-auto tabular-nums text-leaf-muted">
                              {s('away', { m: p.distance_m })}
                            </span>
                          )}
                        </span>
                        <span>
                          {s('battery', { pct: p.battery_pct ?? '?' })}
                          {p.range_m != null &&
                            ` · ${s('range', { km: Math.round(p.range_m / 1000) })}`}
                        </span>
                        {p.price && (
                          <span>{localPrice(p.price, t, i18n.language)}</span>
                        )}
                        {url && (
                          <a
                            className="font-medium text-leaf-forest underline underline-offset-2"
                            href={url}
                            rel="noreferrer"
                            target="_blank"
                          >
                            {s('rent', { provider: p.provider })}
                          </a>
                        )}
                      </li>
                    )
                  })}
                </ul>
              ) : (
                <p className="text-xs text-leaf-muted">{s('setStartHint')}</p>
              )}

              <p className="text-[11px] text-leaf-muted">
                {s('updated', {
                  time: formatTime(vehicles.updated, i18n.language),
                })}{' '}
                · {vehicles.attribution}
              </p>
            </>
          )}
        </section>
      </div>
    </Card>
  )
}

/** The three steps of a rented-vehicle trip, with time, price and the parking rules legend. */
function TripSteps({
  trip,
  s,
  name,
}: {
  trip: SharingTrip
  s: (_key: string, _values?: Record<string, unknown>) => string
  name: (_v: VehicleProperties['vehicle']) => string
}) {
  const { i18n } = useTranslation()
  const [walk1, ride, walk2] = trip.legs
  const v = trip.vehicle.properties
  const rp = trip.return_point.properties
  const price = priceFor(v.price, trip.ride_s)
  const url = safeRentUrl(v.rent_url)
  const where =
    rp.rule === 'parking_zone' && rp.name
      ? s('leaveAtZone', { zone: rp.name })
      : rp.at_destination
        ? s('leaveAtEnd')
        : s('leaveOutside')

  return (
    <div className="flex flex-col gap-2 rounded-xl bg-leaf-cream/70 p-3 text-xs text-leaf-ink/80">
      <p className="text-sm font-medium text-leaf-ink">
        {s('total', { min: minutes(trip.duration_s) })}
        {price !== null &&
          ` · ${s('about', {
            price: price.toLocaleString(i18n.language, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }),
          })}`}
        {` · ${s('kcal', { kcal: Math.round(trip.kcal) })}`}
      </p>
      <ol className="flex list-decimal flex-col gap-1 pl-4">
        <li>
          {s('stepWalkTo', {
            m: Math.round(walk1.properties.length_m),
            min: minutes(walk1.properties.duration_s),
            vehicle: name(v.vehicle),
            pct: v.battery_pct ?? '?',
          })}
        </li>
        <li>
          {s('stepRide', {
            km: km(ride.properties.length_m),
            min: minutes(trip.ride_s),
            where,
          })}
          {ride.properties.pushed_m > 0 &&
            ` ${s('pushed', { m: ride.properties.pushed_m })}`}
        </li>
        {walk2.properties.length_m > 0 && (
          <li>
            {s('stepWalkEnd', {
              m: Math.round(walk2.properties.length_m),
              min: minutes(walk2.properties.duration_s),
            })}
          </li>
        )}
      </ol>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-leaf-muted">
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className="inline-block h-2 w-3 rounded-sm bg-[#e53935]/60"
          />
          {s('noParking', { vehicle: name(v.vehicle) })}
        </span>
        <span className="flex items-center gap-1">
          <span
            aria-hidden
            className="inline-block h-2 w-3 rounded-sm bg-[#fb8c00]/60"
          />
          {s('zonesOnly')}
        </span>
      </div>
      {url && (
        <a
          className="font-medium text-leaf-forest underline underline-offset-2"
          href={url}
          rel="noreferrer"
          target="_blank"
        >
          {s('rentThis', { provider: v.provider })}
        </a>
      )}
      <p className="text-[11px] text-leaf-muted">{trip.attribution}</p>
    </div>
  )
}

/** One row of the trip comparison: label key and how to show a trip's value. */
const TRIP_ROWS: Array<{
  key: string
  format: (_trip: SharingTrip, _language: string) => string
}> = [
  { key: 'doorToDoor', format: trip => `${minutes(trip.duration_s)} min` },
  { key: 'walk', format: trip => `${Math.round(trip.walk_m)} m` },
  {
    key: 'ride',
    format: (trip, lang) =>
      `${(trip.ride_m / 1000).toLocaleString(lang, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`,
  },
  {
    key: 'price',
    format: (trip, lang) => {
      const price = priceFor(trip.vehicle.properties.price, trip.ride_s)
      return price === null
        ? '–'
        : price.toLocaleString(lang, { style: 'currency', currency: 'EUR' })
    },
  },
  { key: 'kcal', format: trip => String(Math.round(trip.kcal)) },
  {
    key: 'roughness',
    format: (trip, lang) =>
      ride(trip.legs[1].properties.mean_roughness, 1, lang),
  },
  {
    key: 'overtaking',
    format: trip => String(trip.legs[1].properties.danger_points),
  },
  {
    key: 'airQuality',
    format: (trip, lang) => ride(trip.legs[1].properties.mean_pm_risk, 2, lang),
  },
  {
    key: 'stopGo',
    format: (trip, lang) => ride(trip.legs[1].properties.mean_stop_go, 2, lang),
  },
]

/** A ride value with fixed decimals, or "–" when nothing was measured. */
function ride(value: number | null, digits: number, language: string) {
  return value == null
    ? '–'
    : value.toLocaleString(language, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      })
}

/** Both line styles of the comparison, as on the map. */
function TripLine({ plain, color }: { plain: boolean; color: string }) {
  return (
    <svg aria-hidden className="h-2 w-6 shrink-0" viewBox="0 0 24 8">
      <line
        stroke={color}
        strokeDasharray={plain ? '4 3' : undefined}
        strokeWidth={plain ? 3.5 : 4.5}
        x1="0"
        x2="24"
        y1="4"
        y2="4"
      />
    </svg>
  )
}

/**
 * The rental trip without any settings (grey dashed, like the shortest route)
 * next to the one with the rider's settings (vehicle colour).
 */
function TripComparison({
  trip,
  plain,
}: {
  trip: SharingTrip
  plain: SharingTrip
}) {
  const { t, i18n } = useTranslation()
  const c = (key: string) => t(`greenest.planTrip.sharing.compare.${key}`)
  const label = (key: string) =>
    ['roughness', 'overtaking', 'airQuality', 'stopGo'].includes(key)
      ? t(`greenest.planTrip.metrics.${key}`)
      : c(key)
  const same =
    JSON.stringify(trip.legs.map(l => l.geometry.coordinates)) ===
    JSON.stringify(plain.legs.map(l => l.geometry.coordinates))
  const columns = [
    {
      trip: plain,
      plain: true,
      color: ROUTE_COLORS.shortest,
      name: c('plain'),
    },
    {
      trip,
      plain: false,
      color: VEHICLE_COLORS[trip.vehicle.properties.vehicle],
      name: c('yours'),
    },
  ]

  return (
    <div className="flex flex-col gap-2 rounded-xl border border-leaf-sand/70 p-3 text-xs">
      <p className="text-sm font-medium text-leaf-ink">{c('title')}</p>
      <table className="w-full border-collapse">
        <thead>
          <tr className="text-left text-leaf-ink">
            <th className="w-2/5 pb-1 font-normal text-leaf-muted" scope="col">
              <span className="sr-only">{c('title')}</span>
            </th>
            {columns.map(col => (
              <th
                className="pb-1 align-top font-semibold"
                key={col.name}
                scope="col"
              >
                <span className="flex items-center gap-1.5">
                  <TripLine color={col.color} plain={col.plain} />
                  {col.name}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {/* Each trip picks its own vehicle (the quickest within reach), so they can differ. */}
          <tr className="border-t border-leaf-sand/50">
            <th
              className="py-1 pr-2 text-left font-normal text-leaf-muted"
              scope="row"
            >
              {c('vehicle')}
            </th>
            {columns.map(col => (
              <td className="py-1 font-medium text-leaf-ink" key={col.name}>
                {t(
                  `greenest.planTrip.sharing.vehicle.${col.trip.vehicle.properties.vehicle}`,
                )}
              </td>
            ))}
          </tr>
          {TRIP_ROWS.map(row => (
            <tr className="border-t border-leaf-sand/50" key={row.key}>
              <th
                className="py-1 pr-2 text-left font-normal text-leaf-muted"
                scope="row"
              >
                {label(row.key)}
              </th>
              {columns.map(col => (
                <td
                  className="py-1 font-medium tabular-nums text-leaf-ink"
                  key={col.name}
                >
                  {row.format(col.trip, i18n.language)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-leaf-muted">{same ? c('same') : c('hint')}</p>
    </div>
  )
}
