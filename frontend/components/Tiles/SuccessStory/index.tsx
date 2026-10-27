import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'

import { getTheme } from '@/lib/api/prismaService'
import Image from 'next/image'
import Markdown from 'react-markdown'
import rehypeExternalLinks from 'rehype-external-links'
import remarkGfm from 'remark-gfm'
import { BaseTile } from '../Base/BaseTile'

export type SuccessStoryTileProps = {
  text: string
  link: string
  image?: string
  imagePosition?: 'left' | 'right' | 'bottom'
  moreInfo?: string
  id: string
}

const normalizeImagePosition = (
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

/**
 * A tile that represents a success story
 * @param SuccessStoryTileProps properties of the success story tile
 * @returns SuccessStoryTileProps
 */
export default async function SuccessStoryTile({
  text,
  // eslint-disable-next-line unused-imports/no-unused-vars
  link,
  image,
  imagePosition = 'left',
  moreInfo,
  id,
}: SuccessStoryTileProps) {
  const theme = await getTheme()
  const normalizedImagePosition = normalizeImagePosition(imagePosition)

  const Content = (
    <div className="flex h-full flex-col justify-between">
      <Title as="h5" font={'semibold'} variant={'primary'}>
        {theme?.successStoriesTitle || 'Erfolgsgeschichten'}
      </Title>
      <Spacer size="md" />
      <Markdown
        className="flex flex-1 flex-col justify-between"
        components={{
          h1: props => (
            <Title
              as={'h2'}
              className="mb-4 md:mb-6"
              variant={'primary'}
              {...props}
            />
          ),
          h2: props => (
            <Title
              as={'h3'}
              className="mb-4 md:mb-6"
              variant={'primary'}
              {...props}
            />
          ),
          h3: props => (
            <Title
              as={'h4'}
              className="mb-4 md:mb-6"
              variant={'primary'}
              {...props}
            />
          ),
          h4: props => <Title as={'h5'} variant={'primary'} {...props} />,
          h5: props => (
            <Title
              as={'h6'}
              className="mb-4 md:mb-6"
              variant={'primary'}
              {...props}
            />
          ),
          h6: props => (
            <Title
              as={'h7'}
              className="mb-4 md:mb-6"
              variant={'primary'}
              {...props}
            />
          ),
          ul: props => <ul className="list-disc px-6" {...props} />,
          p: props => (
            <Title
              as="h3"
              className="mb-6 md:mb-8"
              variant={'primary'}
              {...props}
            />
          ),
        }}
        rehypePlugins={[
          [rehypeExternalLinks, { target: '_blank', rel: 'noopener' }],
        ]}
        remarkPlugins={[remarkGfm]}
      >
        {text}
      </Markdown>
    </div>
  )

  if (!image) {
    return <BaseTile variant="successStory">{Content}</BaseTile>
  }

  const StoryImage = (
    <div className="relative min-h-[20rem] w-full overflow-hidden md:min-h-0 md:w-4/5">
      <Image
        alt="Image"
        className="h-full w-full object-cover object-left"
        height={1200}
        sizes="(min-width: 768px) 40vw, 100vw"
        src={image}
        width={1600}
      />
    </div>
  )

  if (normalizedImagePosition === 'right') {
    return (
      <BaseTile
        embedId={`successStory-${id}`}
        endImage={StoryImage}
        moreInfo={moreInfo}
        variant="successStory"
      >
        {Content}
      </BaseTile>
    )
  }

  if (normalizedImagePosition === 'bottom') {
    const BottomImage = (
      <div className="relative h-[18rem] w-full overflow-hidden md:h-[28rem]">
        <Image
          alt="Image"
          className="object-contain object-center"
          fill
          sizes="100vw"
          src={image}
        />
      </div>
    )
    return (
      <BaseTile
        bottomImage={BottomImage}
        embedId={`successStory-${id}`}
        moreInfo={moreInfo}
        variant="successStory"
      >
        {Content}
      </BaseTile>
    )
  }

  return (
    <BaseTile
      embedId={`successStory-${id}`}
      moreInfo={moreInfo}
      startImage={StoryImage}
      variant="successStory"
    >
      {Content}
    </BaseTile>
  )
}
