# Copilot instructions for this repo

## Big picture architecture

- **Next.js App Router**: UI lives under `app/` with server components by default (e.g., `app/(main)/page.tsx`, `app/(main)/layout.tsx`). Pages use `export const revalidate = 10` for ISR.
- **Tiles as composable units**: Tiles are assembled via `utils/TileFactory.tsx` (string `tileId` → React component) and rendered in layouts via `utils/fullWidthBucket.ts` + `components/Tiles/TileLayout.tsx` to bucket full-width vs column tiles.
- **Content/data layer**: `lib/api/prismaService.ts` is the main service layer that mirrors a Directus-like API using Prisma models defined in `prisma/schema.prisma`. It resolves translations using the active locale from `lib/i18n.ts`.
- **API routes**: Server APIs live in `app/api/**/route.ts` with caching via `@isaacs/ttlcache` (see `app/api/ecocounter/route.ts`, `app/api/neosens/route.ts`) and ISR revalidation via `app/api/revalidate/route.ts`.
- **Static datasets**: CSV/JSON data lives in `assets/data/`; CSVs are imported using webpack `csv-loader` configured in `next.config.js`.

## Key conventions & patterns

- **Locale resolution**: `lib/i18n.ts` reads a `lang` cookie and falls back to the first configured language in `appOptions` (via Prisma). When adding translated fields, follow the `*Translation` tables and `resolveTranslation` helper in `prismaService.ts`.
- **Tile identity**: `TileFactory` uses `tileId` strings like `climate-weather` or `mobility-bicycle` (see `types/tile.d.ts` for prefixes), and special items `survey` / `successStory`. New tiles should register here and in Prisma `Tile.tileId`.
- **Collections/pages**: `/sammlung/[slug]` uses `getCollections()` → `getCollection()` and buckets tiles. `generateStaticParams` returns empty during production build (see `app/sammlung/[slug]/page.tsx`).
- **Prisma client**: `lib/prisma.ts` uses the `@prisma/adapter-pg` with a shared `pg` pool stored on `global` to avoid hot-reload connection storms.

## Developer workflows (from repo scripts)

- Dev server: `npm run dev` (uses `NODE_OPTIONS='--inspect'` for debugging).
- Build/serve: `npm run build`, `npm run start`.
- Lint: `npm run lint`.
- Icons: `npm run svg` generates React icons into `components/Icons/` from `svgicons/`.

## External dependencies & integrations

- **Database**: PostgreSQL via Prisma (`DATABASE_URL` required). Content models and translations live in `prisma/schema.prisma`.
- **Third-party APIs**: Eco-Counter and NeoSens are called in API routes with TTL caching (`app/api/ecocounter`, `app/api/neosens`).
- **Images**: Next Image is configured to allow remote images from `*.reedu.de`, `localhost`, and `nbg1.your-objectstorage.com` (see `next.config.js`).

## Where to look for changes

- New content/data features: `lib/api/prismaService.ts` + `prisma/schema.prisma` + `components/Tiles/**`.
- Routing/layout tweaks: `app/(main)/layout.tsx`, `app/layout.tsx`, `components/Layout/**`.
- Data formatting helpers: `utils/chartFormatter.ts`, `utils/tileLayout.ts`, `utils/tileUtils.tsx`.
