'use client'

import AnimatedNumber from '@/components/Elements/Animated/AnimatedNumber'
import Title from '@/components/Elements/Title'
import { AnimatedProps } from '@react-spring/web'
import { ComponentPropsWithRef } from 'react'

export type SurveyAnswerProps = AnimatedProps<ComponentPropsWithRef<'div'>> & {
  percent: number
  text: string
  unit?: string
}

export default function SurveyAnswer({
  percent,
  text,
  unit,
}: SurveyAnswerProps) {
  return (
    <div className="flex w-full flex-col gap-4">
      <Title as="h1" className="flex-[2_2_0%] whitespace-nowrap">
        {typeof percent === 'number' ? (
          <AnimatedNumber decimals={1}>{percent}</AnimatedNumber>
        ) : (
          <span>--</span>
        )}
        <span className="font-normal">{' ' + unit}</span>
      </Title>

      <Title as="h4" className="flex-[3_3_0%]">
        {text}
      </Title>
    </div>
  )
}
