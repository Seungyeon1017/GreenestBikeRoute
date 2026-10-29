import { cx } from 'class-variance-authority'
import {
  BedDouble,
  Bus,
  Church,
  Coffee,
  GraduationCap,
  Hospital,
  House,
  Landmark,
  type LucideIcon,
  Map as MapIcon,
  MapPin,
  ShoppingBag,
  Signpost,
  SquareParking,
  TrainFront,
  Trees,
  Utensils,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'

/** What kind of place a `/geocode` candidate is, for its icon in the search list. */
export type PlaceKind =
  | 'sbahn'
  | 'train'
  | 'bus'
  | 'street'
  | 'park'
  | 'address'
  | 'food'
  | 'cafe'
  | 'education'
  | 'health'
  | 'worship'
  | 'parking'
  | 'shopping'
  | 'sight'
  | 'hotel'
  | 'area'
  | 'place'

const TYPES: Record<string, Record<string, PlaceKind>> = {
  // Heilbronn's only trams are the Stadtbahn (S4, S41, S42): OSM maps its street stops as tram stops.
  railway: {
    tram_stop: 'sbahn',
    stop: 'sbahn',
    station: 'train',
    halt: 'train',
    platform: 'train',
    railway: 'train',
  },
  highway: { bus_stop: 'bus' },
  amenity: {
    bus_station: 'bus',
    restaurant: 'food',
    fast_food: 'food',
    biergarten: 'food',
    pub: 'food',
    bar: 'food',
    cafe: 'cafe',
    ice_cream: 'cafe',
    school: 'education',
    university: 'education',
    college: 'education',
    kindergarten: 'education',
    library: 'education',
    hospital: 'health',
    clinic: 'health',
    doctors: 'health',
    pharmacy: 'health',
    place_of_worship: 'worship',
    parking: 'parking',
    bicycle_parking: 'parking',
    townhall: 'sight',
    theatre: 'sight',
    events_venue: 'sight',
  },
  landuse: {
    railway: 'train',
    forest: 'park',
    grass: 'park',
    meadow: 'park',
    vineyard: 'park',
  },
  tourism: { hotel: 'hotel', guest_house: 'hotel', hostel: 'hotel' },
}

/** Kinds for a whole OSM category, when its type isn't listed above. */
const CATEGORIES: Record<string, PlaceKind> = {
  highway: 'street',
  leisure: 'park',
  natural: 'park',
  building: 'address',
  shop: 'shopping',
  tourism: 'sight',
  historic: 'sight',
  boundary: 'area',
}

export function placeKind(
  category: string | null,
  type: string | null,
): PlaceKind {
  if (category === 'place') {
    return type === 'house' ? 'address' : 'area'
  }
  return (
    (category && type && TYPES[category]?.[type]) ||
    (category && CATEGORIES[category]) ||
    'place'
  )
}

const ICONS: Record<Exclude<PlaceKind, 'sbahn'>, LucideIcon> = {
  train: TrainFront,
  bus: Bus,
  street: Signpost,
  park: Trees,
  address: House,
  food: Utensils,
  cafe: Coffee,
  education: GraduationCap,
  health: Hospital,
  worship: Church,
  parking: SquareParking,
  shopping: ShoppingBag,
  sight: Landmark,
  hotel: BedDouble,
  area: MapIcon,
  place: MapPin,
}

/** The icon of a search result's kind; the S-Bahn gets the white S on a green disc. */
export default function PlaceIcon({
  category,
  type,
  className,
}: {
  category: string | null
  type: string | null
  className?: string
}) {
  const { t } = useTranslation()
  const kind = placeKind(category, type)
  const label = t(`greenest.planTrip.search.kind.${kind}`)
  if (kind === 'sbahn') {
    return (
      <span
        aria-label={label}
        className={cx(
          'flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[#408335] text-[13px] font-bold leading-none text-white',
          className,
        )}
        role="img"
        title={label}
      >
        S
      </span>
    )
  }
  const Icon = ICONS[kind]
  return (
    <span
      aria-label={label}
      className={cx(
        'flex h-5 w-5 shrink-0 items-center justify-center',
        className,
      )}
      role="img"
      title={label}
    >
      <Icon aria-hidden className="h-4 w-4 text-leaf-forest" />
    </span>
  )
}
