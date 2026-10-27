/**
 * Latin names of species not native to Europe.
 * These are excluded from the bird tile statistics.
 */
const NON_EUROPEAN_SPECIES = new Set([
  // Parakeets & Parrots (non-native; some have established feral colonies in European cities)
  'Psittacula krameri', // Rose-ringed Parakeet
  'Poecile atricapillus',
  'Anhinga anhinga',
  'Mimus polyglottos',
  'Poecile carolinensis',
  'Kanadagans',
  'Branta canadensis',
  'Aphelocoma californica',
  'Psittacula eupatria', // Alexandrine Parakeet
  'Myiopsitta monachus', // Monk Parakeet
  'Amazona amazonica', // Orange-winged Amazon
  'Amazona aestiva', // Turquoise-fronted Amazon
  'Amazona farinosa', // Mealy Amazon
  'Ara ararauna', // Blue-and-yellow Macaw
  'Ara chloropterus', // Red-and-green Macaw
  'Aratinga solstitialis', // Sun Parakeet
  'Brotogeris chiriri', // Yellow-chevroned Parakeet
  'Forpus coelestis', // Pacific Parrotlet
  'Agapornis roseicollis', // Rosy-faced Lovebird
  // Australian species
  'Melopsittacus undulatus', // Budgerigar
  'Nymphicus hollandicus', // Cockatiel
  'Cacatua galerita', // Sulphur-crested Cockatoo
  'Cacatua sulphurea', // Yellow-crested Cockatoo
  'Cacatua roseicapilla', // Galah
  'Platycercus elegans', // Crimson Rosella
  'Platycercus eximius', // Eastern Rosella
  // African species
  'Serinus mozambicus', // Yellow-fronted Canary
  'Estrilda astrild', // Common Waxbill
  'Acridotheres tristis', // Common Myna
  // Asian species
  'Lonchura punctulata', // Scaly-breasted Munia
  'Padda oryzivora', // Java Sparrow
  'Lonchura oryzivora', // Java Sparrow (synonym)
  // North American species
  'Turdus migratorius', // American Robin
  'Cardinalis cardinalis', // Northern Cardinal
  'Cyanocitta cristata', // Blue Jay
  'Corvus brachyrhynchos', // American Crow
  'Quiscalus quiscula', // Common Grackle
  'Molothrus ater', // Brown-headed Cowbird
  'Passerina cyanea', // Indigo Bunting
  'Spinus tristis', // American Goldfinch
  'Junco hyemalis', // Dark-eyed Junco
  'Zonotrichia albicollis', // White-throated Sparrow
  'Melospiza melodia', // Song Sparrow
  'Setophaga coronata', // Yellow-rumped Warbler
  'Setophaga petechia', // American Yellow Warbler
  'Zenaida macroura', // Mourning Dove
])

export function isEuropeanBird(latinName: string): boolean {
  return !NON_EUROPEAN_SPECIES.has(latinName)
}
