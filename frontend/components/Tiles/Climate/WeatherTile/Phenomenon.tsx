import AnimatedNumber from '@/components/Elements/Animated/AnimatedNumber'
import Title from '@/components/Elements/Title'
import {
  MsKlimadashboardIconsWetterNiederschlag,
  MsKlimadashboardIconsWetterSonnig,
  MsKlimadashboardIconsWetterTemperatur,
  MsKlimadashboardIconsWetterWindgeschw,
  MsKlimadashboardIconsWetterWolkendichte,
} from '@/components/Icons/Klima'
import useDevice from '@/hooks/useDevice'
import { cx } from 'class-variance-authority'
import { ForwardRefExoticComponent, JSX, SVGProps } from 'react'
import { useTranslation } from 'react-i18next'

type PhenomenaType = {
  [key: string]: {
    titleKey: string
    shortTitleKey?: string
    unit: string
    icon:
      | ForwardRefExoticComponent<SVGProps<SVGSVGElement>>
      | ((_props: SVGProps<SVGSVGElement>) => JSX.Element)
      | React.ForwardRefExoticComponent<
          Omit<React.SVGProps<SVGSVGElement>, 'ref'> & {
            title?: string | undefined
            titleId?: string | undefined
          } & React.RefAttributes<SVGSVGElement>
        >
    decimals?: number
  }
}

const phenomena: PhenomenaType = {
  temperature: {
    titleKey: 'weatherTile.temperature',
    unit: '\u00b0C',
    icon: MsKlimadashboardIconsWetterTemperatur,
    decimals: 0,
  },
  precipitation: {
    titleKey: 'weatherTile.precipitation',
    unit: 'mm',
    icon: MsKlimadashboardIconsWetterNiederschlag,
  },
  cloudcover: {
    titleKey: 'weatherTile.cloudcover',
    shortTitleKey: 'weatherTile.cloudcoverShort',
    unit: '%',
    icon: MsKlimadashboardIconsWetterWolkendichte,
  },
  windspeed: {
    titleKey: 'weatherTile.windspeed',
    shortTitleKey: 'weatherTile.windspeedShort',
    unit: 'km/h',
    icon: MsKlimadashboardIconsWetterWindgeschw,
    decimals: 1,
  },
  sunhours: {
    titleKey: 'weatherTile.sunhours',
    unit: 'h',
    icon: MsKlimadashboardIconsWetterSonnig,
  },
  no2: {
    titleKey: 'weatherTile.no2',
    unit: '\u03bcg/m\u00b3',
    icon: MsKlimadashboardIconsWetterSonnig,
  },
  pm10: {
    titleKey: 'weatherTile.pm10',
    unit: '\u03bcg/m\u00b3',
    icon: MsKlimadashboardIconsWetterSonnig,
  },
  o3: {
    titleKey: 'weatherTile.o3',
    unit: '\u03bcg/m\u00b3',
    icon: MsKlimadashboardIconsWetterSonnig,
  },
  pm25: {
    titleKey: 'weatherTile.pm25',
    unit: '\u03bcg/m\u00b3',
    icon: MsKlimadashboardIconsWetterSonnig,
  },
}

type PhenomenonProps = {
  phenomenon: keyof typeof phenomena
  value: number
  icon?:
    | ForwardRefExoticComponent<SVGProps<SVGSVGElement>>
    | ((_props: SVGProps<SVGSVGElement>) => JSX.Element)
  size?: 'md' | 'xl'
}

export default function Phenomenon({
  phenomenon,
  value,
  icon,
  size = 'md',
}: PhenomenonProps) {
  const { t } = useTranslation()
  const {
    titleKey,
    unit,
    icon: phenomIcon,
    decimals,
    shortTitleKey,
  } = phenomena[phenomenon]

  const title = t(titleKey)
  const shortTitle = shortTitleKey ? t(shortTitleKey) : undefined

  const valueSize: 'h1' | 'h4' = size === 'xl' ? 'h1' : 'h4'

  const device = useDevice()

  const Icon = icon ? icon : phenomIcon

  return (
    <div className="my-1 flex items-center gap-3 md:my-2">
      <Icon
        className={cx(
          size === 'md' ? 'aspect-square' : 'w-6',
          icon ? '' : 'fill-primary stroke-primary text-primary',
          'h-10 md:h-14',
        )}
      />
      <div>
        <Title
          as={'h5'}
          dangerouslySetInnerHTML={{
            __html: device === 'mobile' && shortTitle ? shortTitle : title,
          }}
          variant={'primary'}
        ></Title>
        <Title as={valueSize} variant="climate">
          {typeof value === 'number' ? (
            <>
              <AnimatedNumber decimals={decimals}>{value}</AnimatedNumber>&nbsp;
              {unit}
            </>
          ) : (
            <>
              <span>--</span>
            </>
          )}{' '}
        </Title>
      </div>
    </div>
  )
}
