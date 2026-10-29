import { type LucideIcon, Map, Route, Sparkles, UserRound } from 'lucide-react'

export type NavTab = {
  href: string
  /** Translation key under `greenest.nav`. */
  key: 'overview' | 'planTrip' | 'highlights' | 'profile'
  icon: LucideIcon
}

/** The primary tabs, in display order. */
export const NAV_TABS: NavTab[] = [
  { href: '/overview', key: 'overview', icon: Map },
  { href: '/plan-trip', key: 'planTrip', icon: Route },
  { href: '/highlights', key: 'highlights', icon: Sparkles },
  { href: '/profile', key: 'profile', icon: UserRound },
]
