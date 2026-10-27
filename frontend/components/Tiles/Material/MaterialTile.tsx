import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'
import SvgHeilbronn from '@/components/Icons/Heilbronn'
import { getMaterials } from '@/lib/api/prismaService'
import { BaseTile } from '../Base/BaseTile'
import MaterialCard from './MaterialCard'

export default async function MaterialTile() {
  const materials = await getMaterials()

  if (materials.length === 0) {
    return null
  }

  return (
    <BaseTile embedId="climate-material" variant="primary">
      <div className="w-full px-2.5">
        <div className="absolute right-16 top-16 hidden lg:block">
          <SvgHeilbronn className="h-[29px] w-auto flex-shrink-0 text-primary opacity-40 md:h-[50px]" />
        </div>
        <div className="flex flex-wrap items-center justify-start gap-x-4 lg:max-w-[87%]">
          <Title as="h1" className="min-w-fit text-primary" font="normal">
            Materialien
          </Title>
        </div>
        <Spacer />
        <div className="space-y-4">
          {materials.map(material => (
            <MaterialCard key={material.id} material={material} />
          ))}
        </div>
        <Spacer />
        <div className="text-xs">
          <Title as="h7" className="inline" font="normal" variant="primary">
            Quelle: Green City Heilbronn
          </Title>
        </div>
      </div>
    </BaseTile>
  )
}
