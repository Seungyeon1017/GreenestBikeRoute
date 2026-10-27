'use client'

import { Button } from '@/components/Elements/Button'
import { Spacer } from '@/components/Elements/Spacer'
import Title from '@/components/Elements/Title'
import { animated, useTransition } from '@react-spring/web'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BaseTile } from '../Base/BaseTile'
import SurveyAnswer, { SurveyAnswerProps } from './Answer'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export type SurveyTileProps = {
  title: string
  question: string
  answer: SurveyAnswerProps
  dataSource: string
  dataRetrieval: Date
  id: string
}
export default function SurveyTile({
  question,
  answer,
  id,
  dataSource,
  dataRetrieval,
  title,
}: SurveyTileProps) {
  const [showAnswer, setShowAnswer] = useState(false)
  const { t } = useTranslation()

  const transitions = useTransition(showAnswer, {
    from: { opacity: 0, y: 80 },
    enter: { opacity: 1, y: 0 },
    leave: { opacity: 0, y: 80 },
    initial: { opacity: 0, y: 0 },
  })

  const RevealAnswerButton = (
    <Button
      className="transition-all"
      onClick={() => setShowAnswer(!showAnswer)}
      variant={'inverse'}
    >
      {showAnswer ? t('survey.hideAnswer') : t('survey.showAnswer')}
    </Button>
  )
  return (
    <BaseTile
      embedId={`survey-${id}`}
      footerCenterElement={RevealAnswerButton}
      variant="secondary"
    >
      <div className="text-white">
        <Title as="h5" font={'normal'} variant={'inverse'}>
          <span className="font-semibold">{title}</span>
        </Title>
        <Spacer />

        <div className="relative h-fit">
          <div className="opacity-0">
            {showAnswer ? (
              <SurveyAnswer {...answer} />
            ) : (
              <Title as="h3" variant={'inverse'}>
                {question}
              </Title>
            )}
          </div>

          {transitions((styles, renderAnswer) =>
            renderAnswer ? (
              <animated.div
                className="absolute left-0 top-0 h-full w-full"
                style={styles}
              >
                <SurveyAnswer {...answer} {...styles} />
              </animated.div>
            ) : (
              // @ts-ignore
              <animated.div
                className="absolute left-0 top-0 h-full w-full"
                style={styles}
              >
                <Title as="h3" variant={'inverse'}>
                  {question}
                </Title>
              </animated.div>
            ),
          )}
        </div>
      </div>
      <Spacer />
      <div className="flex space-x-2 text-xs">
        <ReactMarkdown
          components={{
            p: props => (
              <Title as="h7" font="semibold" variant={'inverse'} {...props} />
            ),

            a: props => (
              <a
                className="underline"
                {...props}
                rel="noopener noreferrer"
                target="_blank"
              />
            ),
          }}
          remarkPlugins={[remarkGfm]}
        >
          {dataSource}
        </ReactMarkdown>
        {/* <Title as="h7" font="semibold" variant={'inverse'}>
          Datenstand: {new Date(dataRetrieval).getFullYear()}
        </Title>
        <Title as="h7" font="normal" variant={'inverse'}>
          Quelle: {dataSource}
        </Title> */}
      </div>
    </BaseTile>
  )
}
