/**
 * Prisma Service Layer
 *
 * This service provides functions that match the existing Directus API
 * while using Prisma for database access. All functions maintain backward
 * compatibility with existing component interfaces.
 */

import { prisma } from '@/lib/prisma'
import { getActiveLocale } from '@/lib/i18n'
import type {
  Collection,
  CollectionWithTiles,
  Datenschutz,
  Impressum,
  Page,
  PageWithTiles,
  SectionWithTiles,
  Status,
  SuccessStory,
  // Removed debug logging
  // console.log('PAGES', pages)
  Survey,
  Theme,
  Tile,
} from '@/lib/types'
import {
  CollectionSchema,
  DatenschutzSchema,
  ImpressumSchema,
  SectionSchema,
  SuccessStorySchema,
  SurveySchema,
  ThemeSchema,
  TileSchema,
  validateOrThrow,
} from '@/lib/validation/schemas'

const resolveTranslation = <T extends { locale: string }>(
  translations: T[] | undefined,
  locale: string,
) => {
  if (!translations || translations.length === 0) {
    return undefined
  }

  return translations.find(t => t.locale === locale) ?? translations[0]
}

/**
 * Tile Operations
 */

/**
 * Get a single tile by its tile_id
 * @param tileId - The tile_id to search for (e.g., 'climate-weather')
 * @returns Tile data or null if not found
 */
export async function getTileData(
  tileId: string,
  locale?: string,
): Promise<Tile | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const tile = await prisma.tile.findFirst({
      where: {
        tileId: tileId,
      },
      include: {
        translations: true,
      },
    })

    if (!tile) {
      return null
    }

    const translation = resolveTranslation(tile.translations, activeLocale)
    const { translations: _translations, ...base } = tile

    return {
      ...base,
      name: translation?.name ?? base.name,
      details: translation?.details ?? base.details,
      info: translation?.info ?? base.info,
    }
  } catch {
    return null
  }
}

/**
 * Get all tiles filtered by status
 * @param status - The status to filter by (DRAFT, PUBLISHED, ARCHIVED)
 * @returns Array of tiles matching the status
 */
export async function getTilesByStatus(
  status: Status,
  locale?: string,
): Promise<Tile[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const tiles = await prisma.tile.findMany({
      where: {
        status: status,
      },
      include: {
        translations: true,
      },
      orderBy: {
        createdAt: 'desc',
      },
    })

    return tiles.map(tile => {
      const translation = resolveTranslation(tile.translations, activeLocale)
      const { translations: _translations, ...base } = tile
      return {
        ...base,
        name: translation?.name ?? base.name,
        details: translation?.details ?? base.details,
        info: translation?.info ?? base.info,
      }
    })
  } catch {
    return []
  }
}

/**
 * Survey Operations
 */

/**
 * Get a single survey by ID
 * @param surveyId - The survey ID
 * @returns Survey data or null if not found
 */
export async function getSurveyData(
  surveyId: string,
  locale?: string,
): Promise<Survey | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const survey = await prisma.survey.findUnique({
      where: {
        id: surveyId,
      },
      include: {
        translations: true,
      },
    })

    if (!survey) {
      return null
    }

    const translation = resolveTranslation(survey.translations, activeLocale)
    const { translations: _translations, ...base } = survey

    return {
      ...base,
      title: translation?.title ?? base.title,
      question: translation?.question ?? base.question,
      answerText: translation?.answerText ?? base.answerText,
      answerValue: translation?.answerValue ?? base.answerValue,
      answerUnit: translation?.answerUnit ?? base.answerUnit,
    }
  } catch {
    return null
  }
}

/**
 * Get all surveys for a specific category
 * @param category - The category to filter by
 * @returns Array of surveys in the category
 */
export async function getSurveysForCategory(
  category: string,
  locale?: string,
): Promise<Survey[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const surveys = await prisma.survey.findMany({
      where: {
        category: category,
        status: 'PUBLISHED',
      },
      include: {
        translations: true,
      },
      orderBy: {
        createdAt: 'desc',
      },
    })

    return surveys.map(survey => {
      const translation = resolveTranslation(survey.translations, activeLocale)
      const { translations: _translations, ...base } = survey
      return {
        ...base,
        title: translation?.title ?? base.title,
        question: translation?.question ?? base.question,
        answerText: translation?.answerText ?? base.answerText,
        answerValue: translation?.answerValue ?? base.answerValue,
        answerUnit: translation?.answerUnit ?? base.answerUnit,
      }
    })
  } catch {
    return []
  }
}

/**
 * Success Story Operations
 */

/**
 * Get a single success story by ID
 * @param storyId - The success story ID
 * @returns Success story data or null if not found
 */
export async function getSuccessStoryData(
  storyId: string,
  locale?: string,
): Promise<SuccessStory | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const story = await prisma.successStory.findUnique({
      where: {
        id: storyId,
      },
      include: {
        translations: true,
      },
    })

    if (!story) {
      return null
    }

    const translation = resolveTranslation(story.translations, activeLocale)
    const { translations: _translations, ...base } = story

    return {
      ...base,
      text: translation?.text ?? base.text,
      details: translation?.details ?? base.details,
    }
  } catch {
    return null
  }
}

/**
 * Get all success stories for a specific category
 * @param category - The category to filter by
 * @returns Array of success stories in the category (limited to 3)
 */
export async function getSuccessStoriesForCategory(
  category: string,
  locale?: string,
): Promise<SuccessStory[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const stories = await prisma.successStory.findMany({
      where: {
        category: category,
        status: 'PUBLISHED',
      },
      include: {
        translations: true,
      },
      orderBy: {
        createdAt: 'desc',
      },
      take: 3,
    })

    return stories.map(story => {
      const translation = resolveTranslation(story.translations, activeLocale)
      const { translations: _translations, ...base } = story
      return {
        ...base,
        text: translation?.text ?? base.text,
        details: translation?.details ?? base.details,
      }
    })
  } catch {
    return []
  }
}

/**
 * Collection Operations
 */

/**
 * Get a single collection by slug with all associated tiles
 * @param slug - The collection slug
 * @returns Collection with tiles or null if not found
 */
export async function getCollection(
  slug: string,
  locale?: string,
): Promise<CollectionWithTiles | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const collection = await prisma.collection.findUnique({
      where: {
        slug: slug,
      },
      include: {
        translations: true,
        tiles: {
          orderBy: {
            sort: 'asc',
          },
        },
      },
    })

    if (!collection) {
      return null
    }

    const translation = resolveTranslation(
      collection.translations,
      activeLocale,
    )
    const { translations: _translations, ...base } = collection

    return {
      ...base,
      title: translation?.title ?? base.title,
      description: translation?.description ?? base.description,
    }
  } catch {
    return null
  }
}

/**
 * Get all collections filtered by status
 * @param status - The status to filter by (DRAFT, PUBLISHED, ARCHIVED)
 * @returns Array of collections matching the status
 */
export async function getCollections(
  status: Status,
  locale?: string,
): Promise<Collection[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const collections = await prisma.collection.findMany({
      where: {
        status: status,
      },
      include: {
        translations: true,
      },
      orderBy: [{ sort: 'asc' }, { createdAt: 'desc' }],
    })

    return collections.map(collection => {
      const translation = resolveTranslation(
        collection.translations,
        activeLocale,
      )
      const { translations: _translations, ...base } = collection
      return {
        ...base,
        title: translation?.title ?? base.title,
        description: translation?.description ?? base.description,
      }
    })
  } catch {
    return []
  }
}

/**
 * Section Operations
 */

/**
 * Get all sections with associated tiles
 * Sections don't have a status field, so all sections are returned
 * @returns Array of sections with tiles
 */
export async function getSections(
  locale?: string,
): Promise<SectionWithTiles[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const sections = await prisma.section.findMany({
      include: {
        translations: true,
        tiles: {
          orderBy: {
            sort: 'asc',
          },
        },
      },
      orderBy: {
        sort: 'asc',
      },
    })

    return sections.map(section => {
      const translation = resolveTranslation(section.translations, activeLocale)
      const { translations: _translations, ...base } = section
      return {
        ...base,
        title: translation?.title ?? base.title,
      }
    })
  } catch {
    return []
  }
}

/**
 * Theme Operations
 */

/**
 * Get the theme configuration
 * There should only be one theme record
 * @returns Theme data or null if not found
 */
export async function getTheme(locale?: string): Promise<Theme | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const theme = await prisma.theme.findFirst({
      orderBy: {
        createdAt: 'desc',
      },
      include: {
        translations: true,
      },
    })

    if (!theme) {
      return null
    }

    const translation = resolveTranslation(theme.translations, activeLocale)
    const { translations: _translations, ...base } = theme

    return {
      ...base,
      title: translation?.title ?? base.title,
      aboutButtonTitle: translation?.aboutButtonTitle ?? base.aboutButtonTitle,
      aboutButtonText: translation?.aboutButtonText ?? base.aboutButtonText,
      successStoriesTitle:
        translation?.successStoriesTitle ?? base.successStoriesTitle,
    }
  } catch {
    return null
  }
}

/**
 * Page Operations
 */

/**
 * Get all pages filtered by status
 * @param status - The status to filter by (DRAFT, PUBLISHED, ARCHIVED)
 * @returns Array of pages matching the status
 */
export async function getPages(
  status: Status,
  locale?: string,
): Promise<Page[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const pages = await prisma.page.findMany({
      where: {
        status: status,
      },
      include: {
        translations: true,
      },
      orderBy: [{ sort: 'asc' }, { createdAt: 'desc' }],
    })
    return pages.map(page => {
      const translation = resolveTranslation(page.translations, activeLocale)
      const { translations: _translations, ...base } = page
      return {
        ...base,
        title: translation?.title ?? base.title,
        description: translation?.description ?? base.description,
      }
    })
  } catch {
    return []
  }
}

/**
 * Get a single page by slug with all associated tiles
 * @param slug - The page slug
 * @returns Page data or null if not found
 */
export async function getPage(
  slug: string,
  locale?: string,
): Promise<PageWithTiles | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const page = await prisma.page.findUnique({
      where: {
        slug: slug,
      },
      include: {
        translations: true,
        tiles: {
          orderBy: {
            sort: 'asc',
          },
        },
        sections: {
          orderBy: {
            sort: 'asc',
          },
        },
      },
    })

    if (!page) {
      return null
    }

    const translation = resolveTranslation(page.translations, activeLocale)
    const { translations: _translations, ...base } = page

    return {
      ...base,
      title: translation?.title ?? base.title,
      description: translation?.description ?? base.description,
    }
  } catch {
    return null
  }
}

/**
 * Get the impressum page content
 * There should only be one impressum record
 * @returns Impressum data or null if not found
 */
export async function getImpressum(locale?: string): Promise<Impressum | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const impressum = await prisma.impressum.findFirst({
      orderBy: {
        createdAt: 'desc',
      },
      include: {
        translations: true,
      },
    })

    if (!impressum) {
      return null
    }

    const translation = resolveTranslation(impressum.translations, activeLocale)
    const { translations: _translations, ...base } = impressum

    return {
      ...base,
      content: translation?.content ?? base.content,
    }
  } catch {
    return null
  }
}

/**
 * Get the datenschutz (privacy policy) page content
 * There should only be one datenschutz record
 * @returns Datenschutz data or null if not found
 */
export async function getDatenschutz(
  locale?: string,
): Promise<Datenschutz | null> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())
    const datenschutz = await prisma.datenschutz.findFirst({
      orderBy: {
        createdAt: 'desc',
      },
      include: {
        translations: true,
      },
    })

    if (!datenschutz) {
      return null
    }

    const translation = resolveTranslation(
      datenschutz.translations,
      activeLocale,
    )
    const { translations: _translations, ...base } = datenschutz

    return {
      ...base,
      content: translation?.content ?? base.content,
    }
  } catch {
    return null
  }
}

/**
 * Dates Operations
 */

/**
 * Get published dates that should be shown on a selected page
 * @param locale - Optional locale override
 * @returns Array of published dates sorted by date descending
 */
export async function getDates(locale?: string): Promise<any[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())

    // Fetch published dates
    const dates = await (prisma as any).dates.findMany({
      where: {
        status: 'PUBLISHED',
      },
      include: {
        translations: true,
      },
      orderBy: {
        startDate: 'desc',
      },
    })

    return dates.map((dateItem: any) => {
      const translation = resolveTranslation(dateItem.translations, activeLocale)
      const { translations: _translations, ...base } = dateItem
      return {
        ...base,
        title: translation?.title ?? base.title,
        description: translation?.description ?? base.description,
      }
    })
  } catch {
    return []
  }
}

/**
 * Get dates configuration (which page to show on)
 * @returns Page slug where dates should be displayed, or null
 */
export async function getDatesPageConfig(): Promise<string | null> {
  try {
    const options = await prisma.appOptions.findFirst()
    return ((options as any)?.showDatesOn || null) as string | null
  } catch {
    return null
  }
}

/**
 * Get all published materials with i18n support
 * @param locale - Optional locale override
 * @returns Array of material items
 */
export async function getMaterials(locale?: string): Promise<any[]> {
  try {
    const activeLocale = locale ?? (await getActiveLocale())

    const materials = await (prisma as any).material.findMany({
      where: {
        status: 'PUBLISHED',
      },
      include: {
        translations: true,
      },
      orderBy: {
        createdAt: 'desc',
      },
    })

    return materials.map((item: any) => {
      const translation = resolveTranslation(item.translations, activeLocale)
      const { translations: _translations, ...base } = item
      return {
        ...base,
        name: translation?.name ?? base.name,
        description: translation?.description ?? base.description,
      }
    })
  } catch {
    return []
  }
}

/**
 * Get material configuration (which page to show on)
 * @returns Page slug where materials should be displayed, or null
 */
export async function getMaterialPageConfig(): Promise<string | null> {
  try {
    const options = await prisma.appOptions.findFirst()
    return ((options as any)?.showMaterialOn || null) as string | null
  } catch {
    return null
  }
}

/**
 * Helper function to fetch related items for collection/section tiles
 * @param junctionItems - Array of junction table items
 * @returns Object with maps of related items by ID
 */
export async function fetchRelatedItemsForJunction(
  junctionItems: Array<{ itemType: string; itemId: string }>,
): Promise<{
  tiles: Map<string, Tile>
  surveys: Map<string, Survey>
  successStories: Map<string, SuccessStory>
}> {
  // Group item IDs by type
  const tileIds = junctionItems
    .filter(item => item.itemType === 'tile')
    .map(item => item.itemId)
  const surveyIds = junctionItems
    .filter(item => item.itemType === 'survey')
    .map(item => item.itemId)
  const storyIds = junctionItems
    .filter(item => item.itemType === 'successStory')
    .map(item => item.itemId)

  // Fetch all related items in parallel
  const [tiles, surveys, stories] = await Promise.all([
    tileIds.length > 0
      ? prisma.tile.findMany({
          where: { id: { in: tileIds } },
        })
      : [],
    surveyIds.length > 0
      ? prisma.survey.findMany({
          where: { id: { in: surveyIds } },
        })
      : [],
    storyIds.length > 0
      ? prisma.successStory.findMany({
          where: { id: { in: storyIds } },
        })
      : [],
  ])

  // Convert arrays to maps for efficient lookup
  return {
    tiles: new Map(tiles.map((tile: Tile) => [tile.id, tile])),
    surveys: new Map(surveys.map((survey: Survey) => [survey.id, survey])),
    successStories: new Map(
      stories.map((story: SuccessStory) => [story.id, story]),
    ),
  }
}

/**
 * Create/Update Operations with Validation
 * These functions validate data before database operations
 */

/**
 * Create a new tile with validation
 * @param data - Tile data to create
 * @returns Created tile
 * @throws Error if validation fails
 */
export async function createTile(data: unknown): Promise<Tile> {
  const validated = validateOrThrow(TileSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...createData
  } = validated

  return await prisma.tile.create({
    data: createData,
  })
}

/**
 * Update an existing tile with validation
 * @param id - Tile ID to update
 * @param data - Tile data to update
 * @returns Updated tile
 * @throws Error if validation fails
 */
export async function updateTile(id: string, data: unknown): Promise<Tile> {
  const validated = validateOrThrow(TileSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...updateData
  } = validated

  return await prisma.tile.update({
    where: { id },
    data: updateData,
  })
}

/**
 * Create a new survey with validation
 * @param data - Survey data to create
 * @returns Created survey
 * @throws Error if validation fails
 */
export async function createSurvey(data: unknown): Promise<Survey> {
  const validated = validateOrThrow(SurveySchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...createData
  } = validated

  return await prisma.survey.create({
    data: {
      ...createData,
      dataSource: createData.dataSource ?? '',
    },
  })
}

/**
 * Update an existing survey with validation
 * @param id - Survey ID to update
 * @param data - Survey data to update
 * @returns Updated survey
 * @throws Error if validation fails
 */
export async function updateSurvey(id: string, data: unknown): Promise<Survey> {
  const validated = validateOrThrow(SurveySchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...updateData
  } = validated

  return await prisma.survey.update({
    where: { id },
    data: {
      ...updateData,
      dataSource: updateData.dataSource ?? '',
    },
  })
}

/**
 * Create a new success story with validation
 * @param data - Success story data to create
 * @returns Created success story
 * @throws Error if validation fails
 */
export async function createSuccessStory(data: unknown): Promise<SuccessStory> {
  const validated = validateOrThrow(SuccessStorySchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...createData
  } = validated

  return await prisma.successStory.create({
    data: {
      ...createData,
      link: createData.link ?? '',
      image: createData.image ?? null,
    },
  })
}

/**
 * Update an existing success story with validation
 * @param id - Success story ID to update
 * @param data - Success story data to update
 * @returns Updated success story
 * @throws Error if validation fails
 */
export async function updateSuccessStory(
  id: string,
  data: unknown,
): Promise<SuccessStory> {
  const validated = validateOrThrow(SuccessStorySchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...updateData
  } = validated

  return await prisma.successStory.update({
    where: { id },
    data: {
      ...updateData,
      link: updateData.link ?? '',
      image: updateData.image ?? null,
    },
  })
}

/**
 * Create a new collection with validation
 * @param data - Collection data to create
 * @returns Created collection
 * @throws Error if validation fails or slug already exists
 */
export async function createCollection(data: unknown): Promise<Collection> {
  const validated = validateOrThrow(CollectionSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...createData
  } = validated

  // Check for slug uniqueness
  const existing = await prisma.collection.findUnique({
    where: { slug: createData.slug },
  })

  if (existing) {
    throw new Error(`Collection with slug "${createData.slug}" already exists`)
  }

  return await prisma.collection.create({
    data: createData,
  })
}

/**
 * Update an existing collection with validation
 * @param id - Collection ID to update
 * @param data - Collection data to update
 * @returns Updated collection
 * @throws Error if validation fails or slug already exists
 */
export async function updateCollection(
  id: string,
  data: unknown,
): Promise<Collection> {
  const validated = validateOrThrow(CollectionSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...updateData
  } = validated

  // Check for slug uniqueness (excluding current record)
  if (updateData.slug) {
    const existing = await prisma.collection.findFirst({
      where: {
        slug: updateData.slug,
        NOT: { id },
      },
    })

    if (existing) {
      throw new Error(
        `Collection with slug "${updateData.slug}" already exists`,
      )
    }
  }

  return await prisma.collection.update({
    where: { id },
    data: updateData,
  })
}

/**
 * Create a new section with validation
 * @param data - Section data to create
 * @returns Created section
 * @throws Error if validation fails
 */
export async function createSection(data: unknown) {
  const validated = validateOrThrow(SectionSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...createData
  } = validated

  return await prisma.section.create({
    data: createData,
  })
}

/**
 * Update an existing section with validation
 * @param id - Section ID to update
 * @param data - Section data to update
 * @returns Updated section
 * @throws Error if validation fails
 */
export async function updateSection(id: string, data: unknown) {
  const validated = validateOrThrow(SectionSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...updateData
  } = validated

  return await prisma.section.update({
    where: { id },
    data: updateData,
  })
}

/**
 * Create or update theme with validation
 * @param data - Theme data to create/update
 * @returns Created or updated theme
 * @throws Error if validation fails
 */
export async function upsertTheme(data: unknown): Promise<Theme> {
  const validated = validateOrThrow(ThemeSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...themeData
  } = validated

  // Check if a theme already exists
  const existingTheme = await prisma.theme.findFirst()

  if (existingTheme) {
    // Update existing theme
    return await prisma.theme.update({
      where: { id: existingTheme.id },
      data: themeData,
    })
  }
  // Create new theme
  return await prisma.theme.create({
    data: themeData,
  })
}

/**
 * Create or update impressum with validation
 * Ensures only one impressum record exists
 * @param data - Impressum data to create/update
 * @returns Created or updated impressum
 * @throws Error if validation fails
 */
export async function upsertImpressum(data: unknown): Promise<Impressum> {
  const validated = validateOrThrow(ImpressumSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...impressumData
  } = validated

  // Check if an impressum already exists
  const existingImpressum = await prisma.impressum.findFirst()

  if (existingImpressum) {
    // Update existing impressum
    return await prisma.impressum.update({
      where: { id: existingImpressum.id },
      data: impressumData,
    })
  }
  // Create new impressum
  return await prisma.impressum.create({
    data: impressumData,
  })
}

/**
 * Create or update datenschutz with validation
 * Ensures only one datenschutz record exists
 * @param data - Datenschutz data to create/update
 * @returns Created or updated datenschutz
 * @throws Error if validation fails
 */
export async function upsertDatenschutz(data: unknown): Promise<Datenschutz> {
  const validated = validateOrThrow(DatenschutzSchema, data)
  const {
    id: _id,
    createdAt: _createdAt,
    updatedAt: _updatedAt,
    ...datenschutzData
  } = validated

  // Check if a datenschutz already exists
  const existingDatenschutz = await prisma.datenschutz.findFirst()

  if (existingDatenschutz) {
    // Update existing datenschutz
    return await prisma.datenschutz.update({
      where: { id: existingDatenschutz.id },
      data: datenschutzData,
    })
  }
  // Create new datenschutz
  return await prisma.datenschutz.create({
    data: datenschutzData,
  })
}

/**
 * Fetch collection by slug
 * @param slug - Slug
 * @param status - Status
 * @returns collection array
 */
export const fetchCollection = async (slug: string, status: string) => {
  const prismaStatus: Status =
    status === 'published'
      ? 'PUBLISHED'
      : status === 'draft'
        ? 'DRAFT'
        : 'ARCHIVED'

  const collection = await prisma.collection.findFirst({
    where: {
      slug: slug,
      status: prismaStatus,
    },
    include: {
      tiles: {
        orderBy: {
          sort: 'asc',
        },
      },
    },
  })

  // Return as array as in the old datamodel
  return collection ? [collection] : []
}

/**
 * Fetch tile type by ID
 * @param id - ID
 * @returns tileId
 */
export const fetchTileType = async (id: string) => {
  try {
    const tile = await prisma.tile.findFirst({
      where: {
        id: id,
      },
      select: {
        tileId: true,
        fullWidth: true,
      },
    })

    return tile
  } catch {
    throw new Error(`Failed to fetch tile: ${id}`)
  }
}
