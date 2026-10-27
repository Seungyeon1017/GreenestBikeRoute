import InsightsContainer, {
  getInsightsData,
} from '@/components/Insights/InsightsContainer'
import Container from '@/components/Layout/Container'

import AnimatedPage from '@/components/Layout/AnimatedPage'

import Title from '@/components/Elements/Title'
import SvgHeilbronn from '@/components/Icons/Heilbronn'
import { TileLayout } from '@/components/Tiles/TileLayout'
import { getSections } from '@/lib/api/prismaService'
import type { SectionWithTiles } from '@/lib/types'
import getTilesBucket from '@/utils/fullWidthBucket'
import { sortTiles } from '@/utils/tileLayout'
import { cx } from 'class-variance-authority'

export default async function Home() {
  const data = await getSections()

  async function buildSections(data: SectionWithTiles[]) {
    const sections = await Promise.all(
      data.map(async section => {
        const { title, tiles, icon } = section

        if (!tiles) {
          return null
        }

        const sortedTiles = sortTiles(tiles)
        const tileBuckets = await getTilesBucket(sortedTiles)

        return (
          <div key={title}>
            <div className="my-4 flex w-full items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="h-14 w-20 rounded-lg border-2 border-primary p-2">
                  <SvgHeilbronn className="mx-auto h-full fill-primary stroke-primary" />
                </div>
                <Title as={'h4'} variant={'primary'}>
                  {title}
                </Title>
              </div>
            </div>
            <TileLayout tileBuckets={tileBuckets} />
          </div>
        )
      }),
    )
    return sections
  }

  const insights = await getInsightsData()

  return (
    <div className={cx(insights.length > 0 && '-translate-y-52')}>
      <AnimatedPage>
        <InsightsContainer />
        <Container>{buildSections(data)}</Container>
      </AnimatedPage>
    </div>
  )
}

export const revalidate = 10
