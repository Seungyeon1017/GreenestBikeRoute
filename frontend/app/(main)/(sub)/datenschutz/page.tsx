import Title from '@/components/Elements/Title'
import Markdown from 'react-markdown'
import rehypeExternalLinks from 'rehype-external-links'
import remarkGfm from 'remark-gfm'
import { getDatenschutz } from '@/lib/api/prismaService'

export default async function Datenschutz() {
  const datenschutz = await getDatenschutz()

  return (
    <main className="mx-auto max-w-[1136px]">
      <Markdown
        components={{
          h1: props => (
            <Title as={'h2'} className="mb-2" variant={'primary'} {...props} />
          ),
          h2: props => (
            <Title as={'h3'} className="mb-2" variant={'primary'} {...props} />
          ),
          h3: props => (
            <Title as={'h4'} className="mb-2" variant={'primary'} {...props} />
          ),
          h4: props => (
            <Title as={'h5'} className="mb-2" variant={'primary'} {...props} />
          ),
          h5: props => (
            <Title as={'h6'} className="mb-2" variant={'primary'} {...props} />
          ),
          h6: props => <Title as={'h7'} className="mb-2" {...props} />,
          ul: props => <ul className="list-disc px-6" {...props} />,
          li: props => (
            <li className="list-disc px-6">
              <Title as="h5" className="mb-4" font={'normal'} {...props} />
            </li>
          ),
          p: props => (
            <Title as="h5" className="mb-4" font={'normal'} {...props} />
          ),
          a: props => <a className="underline" {...props} />,
        }}
        rehypePlugins={[
          [rehypeExternalLinks, { target: '_blank', rel: 'noopener' }],
        ]}
        remarkPlugins={[remarkGfm]}
      >
        {datenschutz?.content || ''}
      </Markdown>
    </main>
  )
}

export const revalidate = 10
