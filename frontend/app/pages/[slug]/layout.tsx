import Back from '@/components/Elements/Back'
import AnimatedPage from '@/components/Layout/AnimatedPage'
import Container from '@/components/Layout/Container'
import Footer from '@/components/Layout/Footer'
import BaseNavbar from '@/components/Layout/Navbar/BaseNavbar'
import Providers from '@/components/Layout/Providers'
import { getPage } from '@/lib/api/prismaService'
import { notFound } from 'next/navigation'

export const revalidate = 10

type Params = Promise<{ slug: string }>

export default async function Layout(props: {
  children: React.ReactNode
  params?: Promise<Params>
}) {
  const params = await props.params
  const { children } = props

  if (!params) {
    return notFound()
  }

  const { slug } = await params

  if (!slug) {
    return notFound()
  }

  const page = await getPage(slug)

  if (!page) {
    return notFound()
  }

  const { title, description } = page

  return (
    <div className="flex h-screen flex-col">
      <BaseNavbar
        actionComponent={<Back />}
        headerDescription={description || ''}
        headerTitle={title}
        variant="secondary"
      />
      <Container className="flex-1">
        <Providers>
          <AnimatedPage>{children}</AnimatedPage>
        </Providers>
      </Container>
      <Footer />
    </div>
  )
}
