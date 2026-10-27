#!/usr/bin/env tsx
/**
 * Directus to Prisma Migration Script
 *
 * This script migrates data from Directus CMS to PostgreSQL via Prisma ORM.
 * It exports all content from Directus, transforms it to match the Prisma schema,
 * validates the data, and imports it into the PostgreSQL database.
 *
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 *
 * Usage:
 *   tsx scripts/migrate-from-directus.ts [--dry-run] [--verbose]
 *
 * Options:
 *   --dry-run   Run migration without committing to database
 *   --verbose   Show detailed logging
 */
import 'dotenv/config'
import { createDirectus, readItems, rest } from '@directus/sdk'
import { prisma } from '../lib/prisma'
import {
  CollectionSchema,
  DatenschutzSchema,
  ImpressumSchema,
  SectionSchema,
  SuccessStorySchema,
  SurveySchema,
  ThemeSchema,
  TileSchema,
  validate,
} from '../lib/validation/schemas'
import type { DirectusStatus } from '../lib/directus'

type Status = 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'
type ImagePosition = 'LEFT' | 'RIGHT' | 'BOTTOM'

// ============================================================================
// Types and Interfaces
// ============================================================================

interface MigrationError {
  recordId: string
  recordType: string
  field?: string
  error: string
}

interface MigrationReport {
  success: boolean
  startTime: Date
  endTime?: Date
  duration?: number
  counts: {
    tiles: { total: number; success: number; failed: number }
    surveys: { total: number; success: number; failed: number }
    successStories: { total: number; success: number; failed: number }
    collections: { total: number; success: number; failed: number }
    sections: { total: number; success: number; failed: number }
    themes: { total: number; success: number; failed: number }
    impressum: { total: number; success: number; failed: number }
    datenschutz: { total: number; success: number; failed: number }
    relationships: { total: number; success: number; failed: number }
  }
  errors: MigrationError[]
}

interface MigrationOptions {
  dryRun: boolean
  verbose: boolean
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Convert Directus status to Prisma Status enum
 */
function convertStatus(status: DirectusStatus | undefined): Status {
  if (!status) {
    return 'PUBLISHED'
  }

  switch (status.toLowerCase()) {
    case 'published':
      return 'PUBLISHED'
    case 'draft':
      return 'DRAFT'
    case 'archived':
      return 'ARCHIVED'
    default:
      return 'PUBLISHED'
  }
}

/**
 * Convert Directus image position to Prisma ImagePosition enum
 */
function convertImagePosition(
  position: 'left' | 'right' | 'bottom' | undefined,
): ImagePosition {
  if (!position) {
    return 'LEFT'
  }
  return position.toUpperCase() as ImagePosition
}

/**
 * Transform Directus image path to match expected format
 * Directus: UUID or filename
 * Prisma: /uploads/filename or full path
 */
function transformImagePath(imagePath: string | undefined): string | undefined {
  if (!imagePath) {
    return undefined
  }

  // If it's already a full path, return as-is
  if (imagePath.startsWith('/') || imagePath.startsWith('http')) {
    return imagePath
  }

  // If it's a UUID or filename, prepend /uploads/
  return `/uploads/${imagePath}`
}

/**
 * Log message with optional verbose mode
 */
function log(
  message: string,
  options: MigrationOptions,
  level: 'info' | 'error' | 'warn' = 'info',
) {
  if (level === 'error' || level === 'warn' || options.verbose) {
    const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : 'ℹ️'
    console.log(`${prefix} ${message}`)
  }
}

/**
 * Initialize migration report
 */
function initReport(): MigrationReport {
  return {
    success: false,
    startTime: new Date(),
    counts: {
      tiles: { total: 0, success: 0, failed: 0 },
      surveys: { total: 0, success: 0, failed: 0 },
      successStories: { total: 0, success: 0, failed: 0 },
      collections: { total: 0, success: 0, failed: 0 },
      sections: { total: 0, success: 0, failed: 0 },
      themes: { total: 0, success: 0, failed: 0 },
      impressum: { total: 0, success: 0, failed: 0 },
      datenschutz: { total: 0, success: 0, failed: 0 },
      relationships: { total: 0, success: 0, failed: 0 },
    },
    errors: [],
  }
}

// ============================================================================
// Directus Data Export
// ============================================================================

/**
 * Export all data from Directus
 */
async function exportFromDirectus(options: MigrationOptions) {
  log('Starting Directus data export...', options)

  const directusUrl = process.env.NEXT_PUBLIC_DIRECTUS_URL
  if (!directusUrl) {
    throw new Error('NEXT_PUBLIC_DIRECTUS_URL environment variable is not set')
  }

  const directus = createDirectus(directusUrl).with(rest())

  log('Fetching tiles...', options)
  const tiles = await directus.request(readItems('tiles', { limit: -1 }))
  log(`Fetched ${tiles.length} tiles`, options)

  log('Fetching surveys...', options)
  const surveys = await directus.request(readItems('survey', { limit: -1 }))
  log(`Fetched ${surveys.length} surveys`, options)

  log('Fetching success stories...', options)
  const successStories = await directus.request(
    readItems('successStory', { limit: -1 }),
  )
  log(`Fetched ${successStories.length} success stories`, options)

  log('Fetching collections...', options)
  const collections = await directus.request(
    readItems('collections', {
      limit: -1,
      fields: ['*', 'tiles.*'],
    }),
  )
  log(`Fetched ${collections.length} collections`, options)

  log('Fetching sections...', options)
  const sections = await directus.request(
    readItems('sections', {
      limit: -1,
      fields: ['*', 'tiles.*'],
    }),
  )
  log(`Fetched ${sections.length} sections`, options)

  log('Fetching theme...', options)
  const themes = await directus.request(readItems('theme', { limit: -1 }))
  log(`Fetched ${themes} theme(s)`, options)

  log('Fetching impressum...', options)
  const impressum = await directus.request(
    readItems('impressum', { limit: -1 }),
  )
  log(`Fetched ${impressum.length} impressum record(s)`, options)

  log('Fetching datenschutz...', options)
  const datenschutz = await directus.request(
    readItems('datenschutz', { limit: -1 }),
  )
  log(`Fetched ${datenschutz.length} datenschutz record(s)`, options)

  log('✅ Directus data export complete', options)

  return {
    tiles,
    surveys,
    successStories,
    collections,
    sections,
    themes,
    impressum,
    datenschutz,
  }
}

// ============================================================================
// Data Transformation and Validation
// ============================================================================

/**
 * Transform and validate tiles
 */
async function transformTiles(
  tiles: any[],
  report: MigrationReport,
  options: MigrationOptions,
): Promise<Map<string, string>> {
  log('Transforming tiles...', options)
  const idMap = new Map<string, string>() // Directus ID -> Prisma ID

  report.counts.tiles.total = tiles.length

  for (const tile of tiles) {
    try {
      const transformed = {
        name: tile.name,
        tileId: tile.tile_id,
        fullWidth: tile.full_width ?? false,
        details: tile.details || null,
        dataUrl: tile.data_url || null,
        info: tile.info || null,
        status: convertStatus(tile.status),
      }

      // Validate
      const validation = validate(TileSchema, transformed)
      if (!validation.success) {
        throw new Error(validation.errors.join(', '))
      }

      if (!options.dryRun) {
        const created = await prisma.tile.create({ data: validation.data })
        idMap.set(tile.id, created.id)
      }

      report.counts.tiles.success++
      log(`✓ Migrated tile: ${tile.name}`, options)
    } catch (error) {
      report.counts.tiles.failed++
      report.errors.push({
        recordId: tile.id,
        recordType: 'tile',
        error: error instanceof Error ? error.message : String(error),
      })
      log(`✗ Failed to migrate tile ${tile.id}: ${error}`, options, 'error')
    }
  }

  return idMap
}

/**
 * Transform and validate surveys
 */
async function transformSurveys(
  surveys: any[],
  report: MigrationReport,
  options: MigrationOptions,
): Promise<Map<string, string>> {
  log('Transforming surveys...', options)
  const idMap = new Map<string, string>()

  report.counts.surveys.total = surveys.length

  for (const survey of surveys) {
    try {
      const transformed = {
        title: survey.title,
        question: survey.question,
        answerText: survey.answer_text,
        answerValue: Number(survey.answer_value),
        answerUnit: survey.answer_unit || '%',
        category: survey.category,
        dataSource: survey.dataSource,
        dataRetrieval: new Date(survey.dataRetrieval),
        status: convertStatus(survey.status),
      }

      // Validate
      const validation = validate(SurveySchema, transformed)
      if (!validation.success) {
        throw new Error(validation.errors.join(', '))
      }

      if (!options.dryRun) {
        const created = await prisma.survey.create({ data: validation.data })
        idMap.set(survey.id, created.id)
      }

      report.counts.surveys.success++
      log(`✓ Migrated survey: ${survey.title}`, options)
    } catch (error) {
      report.counts.surveys.failed++
      report.errors.push({
        recordId: survey.id,
        recordType: 'survey',
        error: error instanceof Error ? error.message : String(error),
      })
      log(`✗ Failed to migrate survey ${survey.id}: ${error}`, options, 'error')
    }
  }

  return idMap
}

/**
 * Transform and validate success stories
 */
async function transformSuccessStories(
  successStories: any[],
  report: MigrationReport,
  options: MigrationOptions,
): Promise<Map<string, string>> {
  log('Transforming success stories...', options)
  const idMap = new Map<string, string>()

  report.counts.successStories.total = successStories.length

  for (const story of successStories) {
    try {
      const transformed = {
        text: story.text,
        link: story.link,
        image: transformImagePath(story.image),
        imagePosition: convertImagePosition(story.image_position),
        category: story.category,
        details: story.details,
        status: convertStatus(story.status),
      }

      // Validate
      const validation = validate(SuccessStorySchema, transformed)
      if (!validation.success) {
        throw new Error(validation.errors.join(', '))
      }

      if (!options.dryRun) {
        const created = await prisma.successStory.create({
          data: validation.data,
        })
        idMap.set(story.id, created.id)
      }

      report.counts.successStories.success++
      log(
        `✓ Migrated success story: ${story.text.substring(0, 50)}...`,
        options,
      )
    } catch (error) {
      report.counts.successStories.failed++
      report.errors.push({
        recordId: story.id,
        recordType: 'successStory',
        error: error instanceof Error ? error.message : String(error),
      })
      log(
        `✗ Failed to migrate success story ${story.id}: ${error}`,
        options,
        'error',
      )
    }
  }

  return idMap
}

/**
 * Transform and validate collections
 */
async function transformCollections(
  collections: any[],
  report: MigrationReport,
  options: MigrationOptions,
): Promise<Map<string, string>> {
  log('Transforming collections...', options)
  const idMap = new Map<string, string>()

  report.counts.collections.total = collections.length

  for (const collection of collections) {
    try {
      const transformed = {
        title: collection.title,
        description: collection.description || null,
        slug: collection.slug,
        image: transformImagePath(collection.image) || '',
        status: convertStatus(collection.status),
      }

      // Validate
      const validation = validate(CollectionSchema, transformed)
      if (!validation.success) {
        throw new Error(validation.errors.join(', '))
      }

      if (!options.dryRun) {
        const created = await prisma.collection.create({
          data: validation.data,
        })
        idMap.set(collection.id, created.id)
      }

      report.counts.collections.success++
      log(`✓ Migrated collection: ${collection.title}`, options)
    } catch (error) {
      report.counts.collections.failed++
      report.errors.push({
        recordId: collection.id,
        recordType: 'collection',
        error: error instanceof Error ? error.message : String(error),
      })
      log(
        `✗ Failed to migrate collection ${collection.id}: ${error}`,
        options,
        'error',
      )
    }
  }

  return idMap
}

/**
 * Transform and validate sections
 */
async function transformSections(
  sections: any[],
  report: MigrationReport,
  options: MigrationOptions,
): Promise<Map<string, string>> {
  log('Transforming sections...', options)
  const idMap = new Map<string, string>()

  report.counts.sections.total = sections.length

  for (const section of sections) {
    try {
      const transformed = {
        title: section.title,
        icon: section.icon || '',
        sort: section.sort || 0,
      }

      // Validate
      const validation = validate(SectionSchema, transformed)
      if (!validation.success) {
        throw new Error(validation.errors.join(', '))
      }

      if (!options.dryRun) {
        const created = await prisma.section.create({ data: validation.data })
        idMap.set(section.id, created.id)
      }

      report.counts.sections.success++
      log(`✓ Migrated section: ${section.title}`, options)
    } catch (error) {
      report.counts.sections.failed++
      report.errors.push({
        recordId: section.id,
        recordType: 'section',
        error: error instanceof Error ? error.message : String(error),
      })
      log(
        `✗ Failed to migrate section ${section.id}: ${error}`,
        options,
        'error',
      )
    }
  }

  return idMap
}

/**
 * Transform and validate theme
 */
async function transformTheme(
  themes: any,
  report: MigrationReport,
  options: MigrationOptions,
) {
  log('Transforming theme...', options)
  console.log(themes)

  report.counts.themes.total = themes.length

  try {
    const transformed = {
      title: themes.title,
      navbarImage: transformImagePath(themes.navbar_image) || '',
      navbarImageLink: themes.navbar_image_link || '/',
      aboutButtonTitle: themes.about_button_title,
      aboutButtonText: themes.about_button_text,
      primary: themes.primary,
      primaryLight: themes.primary_light,
      secondary: themes.secondary,
      secondaryLight: themes.secondary_light,
      climate: themes.climate,
      climateLight: themes.climate_light,
      buildings: themes.buildings,
      buildingsLight: themes.buildings_light,
      mobility: themes.mobility,
      mobilityLight: themes.mobility_light,
      energy: themes.energy,
      energyLight: themes.energy_light,
      borderRadius: themes.border_radius,
      font: themes.font,
      successStoriesTitle: themes.success_stories_title,
      favIcon: transformImagePath(themes.fav_icon) || '',
      openGraphImage: transformImagePath(themes.open_graph_image) || '',
    }

    // Validate
    const validation = validate(ThemeSchema, transformed)
    if (!validation.success) {
      throw new Error(validation.errors.join(', '))
    }

    if (!options.dryRun) {
      await prisma.theme.create({ data: validation.data })
    }

    report.counts.themes.success++
    log(`✓ Migrated theme: ${themes.title}`, options)
  } catch (error) {
    report.counts.themes.failed++
    report.errors.push({
      recordId: themes.id,
      recordType: 'theme',
      error: error instanceof Error ? error.message : String(error),
    })
    log(`✗ Failed to migrate theme ${themes.id}: ${error}`, options, 'error')
  }
}

/**
 * Transform and validate impressum
 */
async function transformImpressum(
  impressum: any,
  report: MigrationReport,
  options: MigrationOptions,
) {
  log('Transforming impressum...', options)

  report.counts.impressum.total = impressum.length

  try {
    const transformed = {
      content: impressum.impressum,
    }

    // Validate
    const validation = validate(ImpressumSchema, transformed)
    if (!validation.success) {
      throw new Error(validation.errors.join(', '))
    }

    if (!options.dryRun) {
      await prisma.impressum.create({ data: validation.data })
    }

    report.counts.impressum.success++
    log('✓ Migrated impressum', options)
  } catch (error) {
    report.counts.impressum.failed++
    report.errors.push({
      recordId: impressum.id,
      recordType: 'impressum',
      error: error instanceof Error ? error.message : String(error),
    })
    log(
      `✗ Failed to migrate impressum ${impressum.id}: ${error}`,
      options,
      'error',
    )
  }
}

/**
 * Transform and validate datenschutz
 */
async function transformDatenschutz(
  datenschutz: any,
  report: MigrationReport,
  options: MigrationOptions,
) {
  log('Transforming datenschutz...', options)

  report.counts.datenschutz.total = datenschutz.length

  try {
    const transformed = {
      content: datenschutz.datenschutz,
    }

    // Validate
    const validation = validate(DatenschutzSchema, transformed)
    if (!validation.success) {
      throw new Error(validation.errors.join(', '))
    }

    if (!options.dryRun) {
      await prisma.datenschutz.create({ data: validation.data })
    }

    report.counts.datenschutz.success++
    log('✓ Migrated datenschutz', options)
  } catch (error) {
    report.counts.datenschutz.failed++
    report.errors.push({
      recordId: datenschutz.id,
      recordType: 'datenschutz',
      error: error instanceof Error ? error.message : String(error),
    })
    log(
      `✗ Failed to migrate datenschutz ${datenschutz.id}: ${error}`,
      options,
      'error',
    )
  }
}

// ============================================================================
// Relationship Migration
// ============================================================================

/**
 * Migrate collection-tile relationships
 */
async function migrateCollectionRelationships(
  collections: any[],
  collectionIdMap: Map<string, string>,
  tileIdMap: Map<string, string>,
  surveyIdMap: Map<string, string>,
  successStoryIdMap: Map<string, string>,
  report: MigrationReport,
  options: MigrationOptions,
) {
  log('Migrating collection relationships...', options)

  for (const collection of collections) {
    if (!collection.tiles || !Array.isArray(collection.tiles)) {
      continue
    }

    const prismaCollectionId = collectionIdMap.get(collection.id)
    if (!prismaCollectionId) {
      log(
        `⚠️  Collection ${collection.id} not found in ID map, skipping relationships`,
        options,
        'warn',
      )
      continue
    }

    for (const tile of collection.tiles) {
      try {
        report.counts.relationships.total++

        // Determine item type and get the new ID
        let itemId: string | undefined
        let itemType: string

        if (tile.collection === 'tiles') {
          itemId = tileIdMap.get(tile.item)
          itemType = 'tile'
        } else if (tile.collection === 'survey') {
          itemId = surveyIdMap.get(tile.item)
          itemType = 'survey'
        } else if (tile.collection === 'successStory') {
          itemId = successStoryIdMap.get(tile.item)
          itemType = 'successStory'
        } else {
          throw new Error(`Unknown collection type: ${tile.collection}`)
        }

        if (!itemId) {
          throw new Error(
            `Item ${tile.item} not found in ${tile.collection} ID map`,
          )
        }

        if (!options.dryRun) {
          await prisma.collectionTile.create({
            data: {
              collectionId: prismaCollectionId,
              itemId,
              itemType,
              sort: tile.sort || 0,
            },
          })
        }

        report.counts.relationships.success++
        log(`✓ Linked ${itemType} to collection ${collection.title}`, options)
      } catch (error) {
        report.counts.relationships.failed++
        report.errors.push({
          recordId: `${collection.id}-${tile.item}`,
          recordType: 'collection_relationship',
          error: error instanceof Error ? error.message : String(error),
        })
        log(`✗ Failed to link item to collection: ${error}`, options, 'error')
      }
    }
  }
}

/**
 * Migrate section-tile relationships
 */
async function migrateSectionRelationships(
  sections: any[],
  sectionIdMap: Map<string, string>,
  tileIdMap: Map<string, string>,
  surveyIdMap: Map<string, string>,
  successStoryIdMap: Map<string, string>,
  report: MigrationReport,
  options: MigrationOptions,
) {
  log('Migrating section relationships...', options)

  for (const section of sections) {
    if (!section.tiles || !Array.isArray(section.tiles)) {
      continue
    }

    const prismaSectionId = sectionIdMap.get(section.id)
    if (!prismaSectionId) {
      log(
        `⚠️  Section ${section.id} not found in ID map, skipping relationships`,
        options,
        'warn',
      )
      continue
    }

    for (const tile of section.tiles) {
      try {
        report.counts.relationships.total++

        // Determine item type and get the new ID
        let itemId: string | undefined
        let itemType: string

        if (tile.collection === 'tiles') {
          itemId = tileIdMap.get(tile.item)
          itemType = 'tile'
        } else if (tile.collection === 'survey') {
          itemId = surveyIdMap.get(tile.item)
          itemType = 'survey'
        } else if (tile.collection === 'successStory') {
          itemId = successStoryIdMap.get(tile.item)
          itemType = 'successStory'
        } else {
          throw new Error(`Unknown collection type: ${tile.collection}`)
        }

        if (!itemId) {
          throw new Error(
            `Item ${tile.item} not found in ${tile.collection} ID map`,
          )
        }

        if (!options.dryRun) {
          await prisma.sectionTile.create({
            data: {
              sectionId: prismaSectionId,
              itemId,
              itemType,
              sort: tile.sort || 0,
            },
          })
        }

        report.counts.relationships.success++
        log(`✓ Linked ${itemType} to section ${section.title}`, options)
      } catch (error) {
        report.counts.relationships.failed++
        report.errors.push({
          recordId: `${section.id}-${tile.item}`,
          recordType: 'section_relationship',
          error: error instanceof Error ? error.message : String(error),
        })
        log(`✗ Failed to link item to section: ${error}`, options, 'error')
      }
    }
  }
}

// ============================================================================
// Report Generation
// ============================================================================

/**
 * Print migration report
 */
function printReport(report: MigrationReport) {
  console.log('\n' + '='.repeat(80))
  console.log('MIGRATION REPORT')
  console.log('='.repeat(80))
  console.log(`Start Time: ${report.startTime.toISOString()}`)
  if (report.endTime) {
    console.log(`End Time: ${report.endTime.toISOString()}`)
    console.log(`Duration: ${report.duration}ms`)
  }
  console.log(`Status: ${report.success ? '✅ SUCCESS' : '❌ FAILED'}`)
  console.log('\n' + '-'.repeat(80))
  console.log('RECORD COUNTS')
  console.log('-'.repeat(80))

  const categories = [
    'tiles',
    'surveys',
    'successStories',
    'collections',
    'sections',
    'themes',
    'impressum',
    'datenschutz',
    'relationships',
  ] as const

  for (const category of categories) {
    const counts = report.counts[category]
    const label = category.charAt(0).toUpperCase() + category.slice(1)
    console.log(
      `${label.padEnd(20)} Total: ${counts.total.toString().padStart(4)} | ` +
        `Success: ${counts.success.toString().padStart(4)} | ` +
        `Failed: ${counts.failed.toString().padStart(4)}`,
    )
  }

  if (report.errors.length > 0) {
    console.log('\n' + '-'.repeat(80))
    console.log('ERRORS')
    console.log('-'.repeat(80))
    for (const error of report.errors) {
      console.log(
        `[${error.recordType}] ${error.recordId}${error.field ? ` (${error.field})` : ''}: ${error.error}`,
      )
    }
  }

  console.log('\n' + '='.repeat(80))
}

// ============================================================================
// Main Migration Function
// ============================================================================

/**
 * Main migration function
 */
async function migrate(options: MigrationOptions) {
  const report = initReport()

  try {
    console.log('\n🚀 Starting Directus to Prisma migration...')
    if (options.dryRun) {
      console.log('⚠️  DRY RUN MODE - No data will be written to database\n')
    }

    // Step 1: Export data from Directus
    const directusData = await exportFromDirectus(options)

    // Step 2: Transform and validate data
    log('\n📦 Transforming and validating data...', options)

    const tileIdMap = await transformTiles(directusData.tiles, report, options)
    const surveyIdMap = await transformSurveys(
      directusData.surveys,
      report,
      options,
    )
    const successStoryIdMap = await transformSuccessStories(
      directusData.successStories,
      report,
      options,
    )
    const collectionIdMap = await transformCollections(
      directusData.collections,
      report,
      options,
    )
    const sectionIdMap = await transformSections(
      directusData.sections,
      report,
      options,
    )

    await transformTheme(directusData.themes, report, options)
    await transformImpressum(directusData.impressum, report, options)
    await transformDatenschutz(directusData.datenschutz, report, options)

    // Step 3: Migrate relationships
    log('\n🔗 Migrating relationships...', options)

    await migrateCollectionRelationships(
      directusData.collections,
      collectionIdMap,
      tileIdMap,
      surveyIdMap,
      successStoryIdMap,
      report,
      options,
    )

    await migrateSectionRelationships(
      directusData.sections,
      sectionIdMap,
      tileIdMap,
      surveyIdMap,
      successStoryIdMap,
      report,
      options,
    )

    // Step 4: Finalize
    report.endTime = new Date()
    report.duration = report.endTime.getTime() - report.startTime.getTime()
    report.success = report.errors.length === 0

    log('\n✅ Migration complete!', options)
  } catch (error) {
    report.endTime = new Date()
    report.duration = report.endTime.getTime() - report.startTime.getTime()
    report.success = false
    report.errors.push({
      recordId: 'MIGRATION',
      recordType: 'system',
      error: error instanceof Error ? error.message : String(error),
    })
    log(`\n❌ Migration failed: ${error}`, options, 'error')
  } finally {
    await prisma.$disconnect()
  }

  return report
}

// ============================================================================
// CLI Entry Point
// ============================================================================

/**
 * Parse command line arguments
 */
function parseArgs(): MigrationOptions {
  const args = process.argv.slice(2)
  return {
    dryRun: args.includes('--dry-run'),
    verbose: args.includes('--verbose'),
  }
}

/**
 * Main entry point
 */
async function main() {
  const options = parseArgs()

  console.log(
    '╔════════════════════════════════════════════════════════════════╗',
  )
  console.log(
    '║         Directus to Prisma Migration Script                   ║',
  )
  console.log(
    '╚════════════════════════════════════════════════════════════════╝',
  )

  const report = await migrate(options)
  printReport(report)

  if (!report.success) {
    process.exit(1)
  }
}

// Run migration if this file is executed directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error)
    process.exit(1)
  })
}

export { migrate, type MigrationOptions, type MigrationReport }
