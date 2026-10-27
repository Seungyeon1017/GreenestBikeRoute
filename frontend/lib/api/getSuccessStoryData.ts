import { SuccessStoryTileProps } from '@/components/Tiles/SuccessStory'
import { getSuccessStoryData as getSuccessStoryDataFromPrisma } from './prismaService'

const mapImagePosition = (
  imagePosition?: string,
): SuccessStoryTileProps['imagePosition'] => {
  switch (imagePosition?.toLowerCase()) {
    case 'right':
      return 'right'
    case 'bottom':
      return 'bottom'
    default:
      return 'left'
  }
}

export const getSuccessStoryData = async (
  successStoryID: string,
  locale?: string,
) => {
  try {
    const data = await getSuccessStoryDataFromPrisma(successStoryID, locale)
    if (!data) {
      return undefined
    }

    const props: SuccessStoryTileProps = {
      id: data.id ?? '',
      link: data.link ?? '',
      text: data.text ?? '',
      image: data.image ?? '',
      imagePosition: mapImagePosition(data.imagePosition),
      moreInfo: data.details ?? '',
    }
    return props
  } catch (e) {
    return undefined
  }
}
