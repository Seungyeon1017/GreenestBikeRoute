import type { HighlightPlace } from '@/types/greenest'

/**
 * Highlights content. Names are real Heilbronn places; descriptions live in
 * messages under `greenest.highlights.places.<id>`. Locations are OSM points
 * (Nominatim); photos are from Wikimedia Commons (public domain or CC BY-SA,
 * credited on the card).
 */
export const SAMPLE_PLACES: HighlightPlace[] = [
  {
    id: 'pfuehlpark',
    name: 'Pfühlpark',
    category: 'park',
    location: [9.2412, 49.14],
    imageUrl: '/highlights/pfuehlpark.jpg',
    imageCredit: {
      author: 'p.schmelzle',
      license: 'Public domain',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Heilbronn-pfuehlpark.jpg',
    },
  },
  {
    id: 'wertwiesenpark',
    name: 'Wertwiesenpark',
    category: 'riverside',
    location: [9.2017, 49.1293],
    imageUrl: '/highlights/wertwiesenpark.jpg',
    imageCredit: {
      author: 'P. Schmelzle',
      license: 'CC BY-SA 3.0 DE',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Wertwiesenpark-heilbronn-2015.jpg',
    },
  },
  {
    id: 'neckarbogen',
    name: 'Neckarbogen',
    category: 'riverside',
    location: [9.2084, 49.1476],
    imageUrl: '/highlights/neckarbogen.jpg',
    imageCredit: {
      author: 'Phlerus',
      license: 'CC BY-SA 4.0',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Neckarbogen_Heilbronn_mit_Blick_auf_den_Flo%C3%9Fhafen.jpg',
    },
  },
  {
    id: 'stadtgarten',
    name: 'Stadtgarten',
    category: 'green-space',
    location: [9.2251, 49.1421],
    imageUrl: '/highlights/stadtgarten.jpg',
    imageCredit: {
      author: 'p.schmelzle',
      license: 'Public domain',
      sourceUrl:
        'https://commons.wikimedia.org/wiki/File:Heilbronn-brunnen-stadtgarten.JPG',
    },
  },
]

/** Themed rides; titles and texts live in messages under `greenest.highlights.experiences`. */
export const EXPERIENCES = [
  'scenicGreen',
  'quietEscape',
  'riverside',
  'nature',
] as const
