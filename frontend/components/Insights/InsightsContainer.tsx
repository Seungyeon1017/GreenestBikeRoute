import { getCollections } from '@/lib/api/prismaService'
import withSuspense from '@/utils/withSuspense'
import Container from '../Layout/Container'
import InsightsCarousel from './InsightsCarousel'

export const getInsightsData = async () => {
  const collections = await getCollections('PUBLISHED')

  // Return only first 3 collections with required fields
  return collections.map(collection => ({
    slug: collection.slug,
    title: collection.title,
    image: collection.image,
  }))
}

async function InsightsContainer() {
  const insights = await getInsightsData()

  if (insights.length === 0) {
    return <></>
  }

  return (
    <div className="w-full">
      <Container className="sm:px-0 px-0 md:px-0 lg:px-0 xl:px-0 2xl:px-0">
        <h1 className="block pb-4 text-center font-lexend text-[30px] font-medium text-primary lg:text-[50px] lg:tracking-tight">
          Unsere Kampagnen
        </h1>
        {insights && <InsightsCarousel insights={insights} />}
      </Container>
    </div>
  )
}

const Fallback = (
  <div className="w-full">
    <Container>
      <div className="flex w-full flex-col items-center justify-between gap-6 lg:flex-row">
        <div className="h-96 w-full flex-1 animate-pulse self-stretch rounded-md bg-zinc-100 lg:rounded-lg" />
        <div className="h-96 w-full flex-1 animate-pulse self-stretch rounded-md bg-zinc-100 lg:rounded-lg" />
        <div className="h-96 w-full flex-1 animate-pulse self-stretch rounded-md bg-zinc-100 lg:rounded-lg" />
      </div>
    </Container>
  </div>
)

export default withSuspense(InsightsContainer, Fallback)
