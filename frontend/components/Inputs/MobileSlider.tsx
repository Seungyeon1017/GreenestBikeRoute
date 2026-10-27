'use client'

import * as SliderPrimitive from '@radix-ui/react-slider'
import { cva, VariantProps } from 'class-variance-authority'
import { useState } from 'react'
import Title from '../Elements/Title'

const sliderStyle = cva('relative h-3 md:h-5 flex-1 rounded-lg', {
  variants: {
    variant: {
      primary: 'bg-primary/20',
      mobility: 'bg-mobility/20',
      successStory: 'bg-secondary/20',
      climate: 'bg-climate/20',
      energy: 'bg-energy/20',
      buildings: 'bg-buildings/20',
    },
  },
  defaultVariants: {
    variant: 'primary',
  },
})

export type SliderProps = SliderPrimitive.SliderProps &
  VariantProps<typeof sliderStyle> & {
    firstValueMobile?: number
    labels?: string[]
  }

export default function MobileSlider({
  firstValueMobile,
  labels,
  variant,
  ...props
}: SliderProps) {
  const [value, setValue] = useState<number>(firstValueMobile || 0)

  return (
    <div>
      <div className="flex w-full items-center">
        {labels && (
          <div className="block">
            <Title as="h5" className="mr-2" variant={'primary'}>
              {labels[value]}
            </Title>
          </div>
        )}
        <SliderPrimitive.Root
          aria-label="Volume"
          className="relative flex h-fit w-full cursor-pointer items-center"
          {...props}
          onValueChange={([e]) => {
            props.onValueChange && props.onValueChange([e])
            setValue(e)
          }}
        >
          <SliderPrimitive.Track className={sliderStyle({ variant })} />
          <SliderPrimitive.Thumb className="block aspect-square h-6 touch-pan-x rounded-full bg-primary shadow shadow-primary md:h-9" />
        </SliderPrimitive.Root>
      </div>
    </div>
  )
}
