import { type LucideIcon, Map, Route, Sparkles } from 'lucide-react'

export type NavTab = {
  href: string
  /** Translation key under `greenest.nav`. */
  key: 'overview' | 'planTrip' | 'highlights'
  icon: LucideIcon
}

/** The three primary tabs, in display order. */
export const NAV_TABS: NavTab[] = [
  { href: '/overview', key: 'overview', icon: Map },
  { href: '/plan-trip', key: 'planTrip', icon: Route },
  { href: '/highlights', key: 'highlights', icon: Sparkles },
]
