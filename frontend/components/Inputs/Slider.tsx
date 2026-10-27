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
    labels?: string[]
    firstValueMobile?: number
    trackHeight?: string // Optional prop for track height
    thumbHeight?: string // Optional prop for thumb height
  }

export default function Slider({
  firstValueMobile,
  labels,
  variant,
  trackHeight = 'md:h-5', // Default height for track
  thumbHeight = 'md:h-9', // Default height for thumb
  ...props
}: SliderProps) {
  const [value, setValue] = useState<number>(firstValueMobile || 0)

  return (
    <div>
      <div className="flex w-full items-center">
        {labels && (
          <div className="block md:hidden">
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
          <SliderPrimitive.Track
            className={sliderStyle({ variant }) + ` ${trackHeight}`}
          />
          <SliderPrimitive.Thumb
            className={`block aspect-square h-6 ${thumbHeight} touch-pan-x rounded-full bg-primary shadow shadow-primary`}
          />
        </SliderPrimitive.Root>
      </div>
      {labels && (
        <div className="mt-3 hidden w-full justify-between md:flex">
          {labels.map((l, i) => (
            <Title as={'h5'} key={i} variant={'primary'}>
              {l}
            </Title>
          ))}
        </div>
      )}
    </div>
  )
}
