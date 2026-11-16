'use client'

import { cx } from 'class-variance-authority'
import { Bike, TrainFront } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import Card, { CardTitle } from '@/components/Greenest/ui/Card'
import InfoTip from '@/components/Greenest/ui/InfoTip'
import type { TrainOption, TrainStop, TrainTrip } from '@/types/greenest'
import { rideOf, TRAIN_RIDE_COLOR, trainLineColor } from './trainLayers'

const TIME_ZONE = 'Europe/Berlin'

const day = (date: Date) =>
  date.toLocaleDateString('en-CA', { timeZone: TIME_ZONE })

/**
 * "08:23" in Heilbronn time, with the weekday in front ("Fri 08:23") when it is on another
 * day than `since` (today when left out).
 */
export function trainTime(iso: string, language: string, since?: string) {
  const date = new Date(iso)
  const sameDay = day(date) === day(since ? new Date(since) : new Date())
  return date.toLocaleTimeString(language, {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TIME_ZONE,
    ...(sameDay ? {} : { weekday: 'short' }),
  })
}

const minutes = (seconds: number) => Math.max(1, Math.round(seconds / 60))
const km = (metres: number, language: string) =>
  (metres / 1000).toLocaleString(language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })

/**
 * A station's name, with the stop the train uses there when the station has several:
 * "Heilbronn Hauptbahnhof (Hbf/Willy-Brandt-Pl.)". The stop's name goes without the words it
 * starts with like the station's ("Heilbronn").
 */
export function stopLabel(stop: Pick<TrainStop, 'name' | 'stop_name'>) {
  if (!stop.stop_name || stop.stop_name === stop.name) {
    return stop.name
  }
  const station = stop.name.split(' ')
  const own = stop.stop_name.split(' ')
  let same = 0
  while (same < own.length - 1 && own[same] === station[same]) {
    same++
  }
  return `${stop.name} (${own.slice(same).join(' ')})`
}

type TrainCardProps = {
  /** The earliest start as "YYYY-MM-DDTHH:mm", or '' for now. */
  departTime: string
  trip: TrainTrip | null
  error: string | null
  loading: boolean
  /** Which of trip.options is shown, here and on the map. */
  optionIndex: number
  onOptionChange: (_index: number) => void
  /** from_train: plan the ride from the station with a rented e-bike instead. */
  onRentFromStation: (_trip: TrainTrip) => void
  /** Riding all the way is there sooner than the first train's trip (both ends in Heilbronn). */
  bikeSooner: boolean
  /** The map shows that ride instead of the train trip: the card only says so. */
  rideInstead: boolean
  onRideInsteadChange: (_on: boolean) => void
}

/**
 * Bike + train: the trip for the start and destination of the form, when "Combine with trains"
 * is on and one of them is a station (both: the train only). Inside Heilbronn the train can be a
 * detour: then the card says riding is sooner and the map shows the bike route, unless the
 * rider asks for the train anyway.
 */
export default function TrainCard(props: TrainCardProps) {
  const { t, i18n } = useTranslation()
  const { trip } = props
  const s = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.train.${key}`, values)
  const option = trip?.options[props.optionIndex] ?? trip?.options[0]
  const direct = trip?.direct
  const first = trip?.options[0]

  return (
    <Card>
      <div className="flex flex-col gap-3">
        {/* relative: the info panel spans this row. */}
        <div className="relative flex items-center gap-1.5">
          <CardTitle>{s('title')}</CardTitle>
          <InfoTip
            label={t('greenest.planTrip.info.about', { name: s('title') })}
          >
            {s('note')}
          </InfoTip>
        </div>
        <p className="text-xs text-leaf-muted">
          {props.departTime
            ? s('earliest.at', {
                time: trainTime(props.departTime, i18n.language),
              })
            : s('earliest.now')}
        </p>
        {props.loading && (
          <p className="text-xs text-leaf-muted" role="status">
            {s('loading')}
          </p>
        )}
        {props.error && (
          <p className="text-xs text-red-700" role="alert">
            {props.error}
          </p>
        )}
        {trip && direct && first && props.bikeSooner && (
          <div className="flex flex-col gap-1.5 rounded-xl bg-leaf-mint p-3 text-xs text-leaf-forest">
            <p>
              {s(props.rideInstead ? 'direct.shown' : 'direct.sooner', {
                bike: trainTime(direct.arrive_at, i18n.language),
                train: trainTime(first.arrive_at, i18n.language),
                min: minutes(direct.duration_s),
                km: km(direct.length_m, i18n.language),
              })}
            </p>
            <button
              className="self-start font-medium underline underline-offset-2"
              onClick={() => props.onRideInsteadChange(!props.rideInstead)}
              type="button"
            >
              {s(props.rideInstead ? 'direct.showTrain' : 'direct.showBike')}
            </button>
          </div>
        )}
        {trip && option && !props.rideInstead && (
          <TrainSteps
            onOptionChange={props.onOptionChange}
            onRentFromStation={props.onRentFromStation}
            option={option}
            optionIndex={props.optionIndex}
            trip={trip}
          />
        )}
      </div>
    </Card>
  )
}

function RideStep({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <Bike
        aria-hidden
        className="mt-0.5 h-4 w-4 shrink-0"
        style={{ color: TRAIN_RIDE_COLOR }}
      />
      <span className="flex min-w-0 flex-col">{children}</span>
    </li>
  )
}

/** The chosen train's trip step by step, the bike rule, and the other trains to pick from. */
function TrainSteps({
  trip,
  option,
  optionIndex,
  onOptionChange,
  onRentFromStation,
}: {
  trip: TrainTrip
  option: TrainOption
  optionIndex: number
  onOptionChange: (_index: number) => void
  onRentFromStation: (_trip: TrainTrip) => void
}) {
  const { t, i18n } = useTranslation()
  const s = (key: string, values?: Record<string, unknown>) =>
    t(`greenest.planTrip.train.${key}`, values)
  // Only the first time of a trip says which day it is; the rest are that day's times.
  const time = (iso: string, since: string = option.leave_at) =>
    trainTime(iso, i18n.language, since)
  const today = new Date().toISOString()
  /** "53 min" or "1 h 9 min". */
  const duration = (seconds: number) => {
    const min = Math.max(1, Math.round(seconds / 60))
    return min < 60
      ? s('duration.min', { min })
      : s('duration.hours', { h: Math.floor(min / 60), min: min % 60 })
  }
  const toTrain = trip.direction === 'to_train'
  // The ride to the stop this train uses: a station can have several, each with its own ride.
  const ride = rideOf(trip, option)?.properties
  const board = trip.board.properties.name
  const alight = trip.alight.properties.name
  const rideFacts = {
    km: km(ride?.length_m ?? 0, i18n.language),
    min: minutes(ride?.duration_s ?? 0),
  }
  const between = option.stops.length - 2
  const platform = (value: string | null) =>
    value ? ` (${s('step.platform', { platform: value })})` : ''

  const trainStep = (
    <li className="flex gap-2">
      <TrainFront
        aria-hidden
        className="mt-0.5 h-4 w-4 shrink-0"
        style={{ color: trainLineColor(option.line) }}
      />
      <span className="flex min-w-0 flex-col">
        <span className="font-medium text-leaf-ink">
          {s('step.train', { line: option.line, headsign: option.headsign })}
        </span>
        <span>
          {stopLabel(option.stops[0])} {time(option.departure)}
          {platform(option.platform)} →{' '}
          {stopLabel(option.stops[option.stops.length - 1])}{' '}
          {time(option.arrival)}
          {platform(option.arrival_platform)}
        </span>
        <span className="text-leaf-muted">
          {s('step.trainFacts', { min: option.duration_min })}
          {between > 0 && ` · ${s('step.stopsBefore', { count: between })}`}
        </span>
      </span>
    </li>
  )

  return (
    <div className="flex flex-col gap-2.5 rounded-xl bg-leaf-cream/70 p-3 text-xs text-leaf-ink/80">
      <div>
        <p className="text-base font-semibold text-leaf-forest">
          {s(`headline.${trip.direction}`, {
            leave: time(option.leave_at, today),
          })}
        </p>
        <p>
          {s(`arrive.${trip.direction}`, {
            station: alight,
            time: time(option.arrive_at),
            duration: duration(option.duration_s),
          })}
        </p>
      </div>

      <ol className="flex flex-col gap-2">
        {!ride ? (
          trainStep
        ) : toTrain ? (
          <>
            <RideStep>
              <span className="font-medium text-leaf-ink">
                {s('step.rideTo', { ...rideFacts, station: board })}
              </span>
              <span className="text-leaf-muted">
                {s('step.wait', {
                  time: time(
                    new Date(
                      new Date(option.departure).getTime() -
                        option.wait_s * 1000,
                    ).toISOString(),
                  ),
                  min: minutes(option.wait_s),
                })}
              </span>
            </RideStep>
            {trainStep}
          </>
        ) : (
          <>
            {trainStep}
            <RideStep>
              <span className="font-medium text-leaf-ink">
                {s('step.rideOn', { ...rideFacts, station: alight })}
              </span>
            </RideStep>
          </>
        )}
      </ol>

      <p
        className={cx(
          'rounded-lg px-2 py-1.5',
          option.bike_ticket_needed
            ? 'bg-amber-100 text-amber-900'
            : 'bg-leaf-mint text-leaf-forest',
        )}
      >
        {s(option.bike_ticket_needed ? 'ticket.needed' : 'ticket.free')}
      </p>

      {trip.options.length > 1 && (
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 font-medium text-leaf-ink">
            {s('others')}
          </legend>
          {trip.options.map((o, i) => (
            <label
              className={cx(
                'flex cursor-pointer items-center gap-2 rounded-lg border px-2 py-1.5',
                i === optionIndex
                  ? 'border-leaf-forest bg-white'
                  : 'border-leaf-sand/70 hover:bg-white/60',
              )}
              key={`${o.departure}-${o.line}`}
            >
              <input
                checked={i === optionIndex}
                className="h-3.5 w-3.5 accent-leaf-forest"
                name="train-option"
                onChange={() => onOptionChange(i)}
                type="radio"
              />
              <span className="whitespace-nowrap font-medium text-leaf-ink">
                {o.line}
              </span>
              <span className="tabular-nums">
                {s(`option.${trip.direction}`, {
                  leave: time(o.leave_at, today),
                  departure: time(o.departure, toTrain ? o.leave_at : today),
                  arrival: time(o.arrival, o.leave_at),
                  arrive: time(o.arrive_at, o.leave_at),
                })}
              </span>
            </label>
          ))}
        </fieldset>
      )}

      {trip.direction === 'from_train' && (trip.shared_bikes_near ?? 0) > 0 && (
        <p>
          {s('shared.count', {
            count: trip.shared_bikes_near ?? 0,
            station: alight,
          })}{' '}
          <button
            className="font-medium text-leaf-forest underline underline-offset-2"
            onClick={() => onRentFromStation(trip)}
            type="button"
          >
            {s('shared.plan')}
          </button>
        </p>
      )}

      {ride && (
        <p className="text-leaf-muted">
          {s('kcal', { kcal: Math.round(ride.kcal) })}
        </p>
      )}
      {!ride && trip.direct && (
        <p className="text-leaf-muted">
          {s('direct.between', {
            min: minutes(trip.direct.duration_s),
            km: km(trip.direct.length_m, i18n.language),
          })}
        </p>
      )}
      <p className="text-[11px] text-leaf-muted">
        {trip.valid_until &&
          s('validUntil', {
            date: new Date(`${trip.valid_until}T12:00`).toLocaleDateString(
              i18n.language,
              { day: 'numeric', month: 'long' },
            ),
          })}{' '}
        {trip.attribution}
      </p>
    </div>
  )
}
