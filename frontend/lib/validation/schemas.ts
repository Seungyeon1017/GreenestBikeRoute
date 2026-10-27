/**
 * Zod validation schemas for all Prisma models
 * These schemas provide runtime validation before database operations
 */

import { z } from 'zod'

// ============================================================================
// Enums
// ============================================================================

export const StatusSchema = z.enum(['DRAFT', 'PUBLISHED', 'ARCHIVED'])

export const ImagePositionSchema = z.enum(['LEFT', 'RIGHT', 'BOTTOM'])

// ============================================================================
// Tile Type Validation
// ============================================================================

// Valid tile type prefixes
const TileTypePrefixSchema = z.enum([
  'climate',
  'mobility',
  'energy',
  'building',
  'survey',
  'successStory',
])

// Valid tile type suffixes for each category
const ClimateTypesSchema = z.enum([
  'weather',
  'co2',
  'indices',
  'development',
  'garbage',
  'data',
  'wachstum',
  'airquality',
])

const MobilityTypesSchema = z.enum([
  'bicycle',
  'stadtradeln',
  'bus',
  'modalSplit',
  'trafficload',
  'awm',
  'masterplan',
  'passengers',
  'bicycleCampaign',
  'bicycleOvertaking',
])

const BuildingsTypesSchema = z.enum([
  'ecoProfit',
  'energyConsumption',
  'renovation',
])

const EnergyTypesSchema = z.enum([
  'PV',
  'wind',
  'PVAnlagen',
  'energietraeger',
  'lanterns',
])

// Custom validator for tile IDs
const TileIdSchema = z.string().refine(
  tileId => {
    // Special cases: survey and successStory can be standalone or with suffix
    if (tileId === 'survey' || tileId.startsWith('survey-')) {
      return true
    }
    if (tileId === 'successStory' || tileId.startsWith('successStory-')) {
      return true
    }

    // Check if it matches the pattern: prefix-suffix
    const parts = tileId.split('-')
    if (parts.length < 2) {
      return false
    }

    const [prefix, ...suffixParts] = parts
    const suffix = suffixParts.join('-')

    // Validate prefix
    const prefixResult = TileTypePrefixSchema.safeParse(prefix)
    if (!prefixResult.success) {
      return false
    }

    // Validate suffix based on prefix
    switch (prefix) {
      case 'climate':
        return ClimateTypesSchema.safeParse(suffix).success
      case 'mobility':
        return MobilityTypesSchema.safeParse(suffix).success
      case 'building':
        return BuildingsTypesSchema.safeParse(suffix).success
      case 'energy':
        return EnergyTypesSchema.safeParse(suffix).success
      case 'survey':
      case 'successStory':
        return true // These can have any suffix (IDs)
      default:
        return false
    }
  },
  {
    message:
      'Invalid tile ID format. Must be in format: prefix-suffix (e.g., climate-weather, mobility-bicycle)',
  },
)

// ============================================================================
// Hex Color Validation
// ============================================================================

const HexColorSchema = z
  .string()
  .regex(
    /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/,
    'Must be a valid hex color code (e.g., #FFF or #FFFFFF)',
  )

// ============================================================================
// Model Schemas
// ============================================================================

/**
 * Tile Schema
 * Validates tile data with tileId validation against TileType enum
 */
export const TileSchema = z.object({
  id: z.string().cuid().optional(),
  name: z.string().min(1, 'Name is required'),
  tileId: TileIdSchema,
  fullWidth: z.boolean().default(false),
  details: z.string().optional().nullable(),
  dataUrl: z.string().url('Must be a valid URL').optional().nullable(),
  info: z.string().optional().nullable(),
  status: StatusSchema.default('PUBLISHED'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type TileInput = z.infer<typeof TileSchema>

/**
 * Survey Schema
 * Validates survey data with numeric answerValue validation
 */
export const SurveySchema = z.object({
  id: z.string().cuid().optional(),
  title: z.string().min(1, 'Title is required'),
  question: z.string().min(1, 'Question is required'),
  answerText: z.string().min(1, 'Answer text is required'),
  answerValue: z
    .number({
      message: 'Answer value must be a number',
    })
    .finite('Answer value must be a finite number'),
  answerUnit: z.string().default('%'),
  category: z.string().min(1, 'Category is required'),
  dataSource: z.string().optional().nullable(),
  dataRetrieval: z.date({
    message: 'Data retrieval must be a valid date',
  }),
  status: StatusSchema.default('PUBLISHED'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type SurveyInput = z.infer<typeof SurveySchema>

/**
 * Success Story Schema
 * Validates success story data
 */
export const SuccessStorySchema = z.object({
  id: z.string().cuid().optional(),
  text: z.string().min(1, 'Text is required'),
  link: z.string().optional(),
  image: z.string().optional().nullable(),
  imagePosition: ImagePositionSchema.default('LEFT'),
  category: z.string().min(1, 'Category is required'),
  details: z.string().min(1, 'Details are required'),
  status: StatusSchema.default('PUBLISHED'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type SuccessStoryInput = z.infer<typeof SuccessStorySchema>

/**
 * Collection Schema
 * Validates collection data with unique slug validation
 * Note: Slug uniqueness is enforced at the database level via unique constraint
 * and should be checked in service functions before insertion
 */
export const CollectionSchema = z.object({
  id: z.string().cuid().optional(),
  title: z.string().min(1, 'Title is required'),
  description: z.string().optional().nullable(),
  slug: z
    .string()
    .min(1, 'Slug is required')
    .regex(
      /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
      'Slug must be lowercase alphanumeric with hyphens only',
    ),
  image: z.string().min(1, 'Image is required'),
  status: StatusSchema.default('PUBLISHED'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type CollectionInput = z.infer<typeof CollectionSchema>

/**
 * Collection Tile Junction Schema
 */
export const CollectionTileSchema = z.object({
  id: z.string().cuid().optional(),
  collectionId: z.string().cuid('Invalid collection ID'),
  itemId: z.string().cuid('Invalid item ID'),
  itemType: z.enum(['tile', 'survey', 'successStory']),
  sort: z.number().int().nonnegative().default(0),
})

export type CollectionTileInput = z.infer<typeof CollectionTileSchema>

/**
 * Section Schema
 */
export const SectionSchema = z.object({
  id: z.string().cuid().optional(),
  title: z.string().min(1, 'Title is required'),
  icon: z.string().min(1, 'Icon is required'),
  sort: z.number().int().nonnegative().default(0),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type SectionInput = z.infer<typeof SectionSchema>

/**
 * Section Tile Junction Schema
 */
export const SectionTileSchema = z.object({
  id: z.string().cuid().optional(),
  sectionId: z.string().cuid('Invalid section ID'),
  itemId: z.string().cuid('Invalid item ID'),
  itemType: z.enum(['tile', 'survey', 'successStory']),
  sort: z.number().int().nonnegative().default(0),
})

export type SectionTileInput = z.infer<typeof SectionTileSchema>

/**
 * Theme Schema
 * Validates theme data with hex color validation
 */
export const ThemeSchema = z.object({
  id: z.string().cuid().optional(),
  title: z.string().min(1, 'Title is required'),
  navbarImage: z.string().min(1, 'Navbar image is required'),
  navbarImageLink: z.string().nullable(),
  aboutButtonTitle: z.string().min(1, 'About button title is required'),
  aboutButtonText: z.string().min(1, 'About button text is required'),
  primary: HexColorSchema,
  primaryLight: HexColorSchema,
  secondary: HexColorSchema,
  secondaryLight: HexColorSchema,
  climate: HexColorSchema,
  climateLight: HexColorSchema,
  buildings: HexColorSchema,
  buildingsLight: HexColorSchema,
  mobility: HexColorSchema,
  mobilityLight: HexColorSchema,
  energy: HexColorSchema,
  energyLight: HexColorSchema,
  borderRadius: z
    .number()
    .int()
    .nonnegative('Border radius must be non-negative'),
  font: z.string().min(1, 'Font is required'),
  successStoriesTitle: z.string().min(1, 'Success stories title is required'),
  favIcon: z.string().min(1, 'Favicon is required'),
  openGraphImage: z.string().min(1, 'Open graph image is required'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type ThemeInput = z.infer<typeof ThemeSchema>

/**
 * Impressum Schema
 */
export const ImpressumSchema = z.object({
  id: z.string().cuid().optional(),
  content: z.string().min(1, 'Content is required'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type ImpressumInput = z.infer<typeof ImpressumSchema>

/**
 * Datenschutz Schema
 */
export const DatenschutzSchema = z.object({
  id: z.string().cuid().optional(),
  content: z.string().min(1, 'Content is required'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
})

export type DatenschutzInput = z.infer<typeof DatenschutzSchema>

// ============================================================================
// Validation Helper Functions
// ============================================================================

/**
 * Validates data against a schema and throws a formatted error if validation fails
 */
export function validateOrThrow<T>(schema: z.ZodSchema<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (!result.success) {
    const errors = result.error.issues
      .map((err: z.ZodIssue) => `${err.path.join('.')}: ${err.message}`)
      .join(', ')
    throw new Error(`Validation failed: ${errors}`)
  }
  return result.data
}

/**
 * Validates data against a schema and returns validation result
 */
export function validate<T>(
  schema: z.ZodSchema<T>,
  data: unknown,
): { success: true; data: T } | { success: false; errors: string[] } {
  const result = schema.safeParse(data)
  if (!result.success) {
    return {
      success: false,
      errors: result.error.issues.map(
        (err: z.ZodIssue) => `${err.path.join('.')}: ${err.message}`,
      ),
    }
  }
  return { success: true, data: result.data }
}
