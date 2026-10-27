// components/TileLayout.tsx
import Columns from '@/components/Layout/Columns'
import { TilesBucket } from '@/utils/fullWidthBucket'
import { renderTileComponents } from '@/utils/tileUtils'

export async function TileLayout({
  tileBuckets,
}: {
  tileBuckets: TilesBucket[]
}) {
  return (
    <>
      {await Promise.all(
        tileBuckets.map(async ({ tiles, isFullWidth }, i) => {
          const components = await renderTileComponents(tiles)
          return isFullWidth ? (
            <div className="w-full" key={i}>{components}</div>
          ) : (
            <Columns key={i}>{components}</Columns>
          )
        }),
      )}
    </>
  )
}
