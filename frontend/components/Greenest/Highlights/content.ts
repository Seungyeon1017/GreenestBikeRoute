import type { HighlightPlace } from '@/types/greenest'

/**
 * SAMPLE CONTENT for the Highlights layout. Names are real Heilbronn places,
 * descriptions are placeholders. Locations are OSM points (Nominatim); photos
 * are from Wikimedia Commons (public domain or CC BY-SA, credited on the card).
 * Every entry is `demo: true` so the card shows a "Sample" badge.
 */
export const SAMPLE_PLACES: HighlightPlace[] = [
  {
    id: 'pfuehlpark',
    name: 'Pfühlpark',
    description: 'Large city park with old trees and quiet paths.',
    category: 'park',
    location: [9.2412, 49.14],
    imageUrl: '/highlights/pfuehlpark.jpg',
    imageCredit: {
      author: 'p.schmelzle',
      license: 'Public domain',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Heilbronn-pfuehlpark.jpg',
    },
    demo: true,
  },
  {
    id: 'wertwiesenpark',
    name: 'Wertwiesenpark',
    description: 'Open park space close to the Neckar.',
    category: 'riverside',
    location: [9.2017, 49.1293],
    imageUrl: '/highlights/wertwiesenpark.jpg',
    imageCredit: {
      author: 'P. Schmelzle',
      license: 'CC BY-SA 3.0 DE',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Wertwiesenpark-heilbronn-2015.jpg',
    },
    demo: true,
  },
  {
    id: 'neckarbogen',
    name: 'Neckarbogen',
    description: 'Riverside quarter with green spaces along the water.',
    category: 'riverside',
    location: [9.2084, 49.1476],
    imageUrl: '/highlights/neckarbogen.jpg',
    imageCredit: {
      author: 'Phlerus',
      license: 'CC BY-SA 4.0',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Neckarbogen_Heilbronn_mit_Blick_auf_den_Flo%C3%9Fhafen.jpg',
    },
    demo: true,
  },
  {
    id: 'stadtgarten',
    name: 'Stadtgarten',
    description: 'Green space in the city centre.',
    category: 'green-space',
    location: [9.2251, 49.1421],
    imageUrl: '/highlights/stadtgarten.jpg',
    imageCredit: {
      author: 'p.schmelzle',
      license: 'Public domain',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Heilbronn-brunnen-stadtgarten.JPG',
    },
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
