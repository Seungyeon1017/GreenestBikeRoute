import type { HighlightPlace } from '@/types/greenest'

/**
 * SAMPLE CONTENT for the Highlights layout. Names are real Heilbronn places,
 * descriptions are placeholders and locations are left out until verified
 * (Phase 5). Every entry is `demo: true` so the card shows a "Sample" badge.
 */
export const SAMPLE_PLACES: HighlightPlace[] = [
  {
    id: 'pfuehlpark',
    name: 'Pfühlpark',
    description: 'Large city park with old trees and quiet paths.',
    category: 'park',
    demo: true,
  },
  {
    id: 'wertwiesenpark',
    name: 'Wertwiesenpark',
    description: 'Open park space close to the Neckar.',
    category: 'riverside',
    demo: true,
  },
  {
    id: 'neckarbogen',
    name: 'Neckarbogen',
    description: 'Riverside quarter with green spaces along the water.',
    category: 'riverside',
    demo: true,
  },
  {
    id: 'stadtgarten',
    name: 'Stadtgarten',
    description: 'Green space in the city centre.',
    category: 'green-space',
    demo: true,
  },
]

/** Themed rides; titles and texts live in messages under `greenest.highlights.experiences`. */
export const EXPERIENCES = [
  'scenicGreen',
  'quietEscape',
  'riverside',
  'nature',
] as const
