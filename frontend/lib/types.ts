// Re-export Prisma types for use throughout the application
import { Prisma } from '@prisma/client'

export type {
  Tile,
  Survey,
  SuccessStory,
  Collection,
  Page,
  Section,
  Theme,
  Impressum,
  Datenschutz,
  Status,
  ImagePosition,
} from '@prisma/client'

// Complex types with relations
// Note: CollectionTile and SectionTile don't have FK relations in schema
// so we need to manually fetch related items
export type CollectionWithTiles = Prisma.CollectionGetPayload<{
  include: {
    tiles: true
    translations: true
  }
}>

export type PageWithTiles = Prisma.PageGetPayload<{
  include: {
    tiles: true
    sections: true
    translations: true
  }
}>

export type SectionWithTiles = Prisma.SectionGetPayload<{
  include: {
    tiles: true
  }
}>

// Junction table item type
export type CollectionTileItem = Prisma.CollectionTileGetPayload<{}>
export type SectionTileItem = Prisma.SectionTileGetPayload<{}>
export type PageTileItem = Prisma.PageTileGetPayload<{}>
export type PageSectionItem = Prisma.PageSectionGetPayload<{}>
