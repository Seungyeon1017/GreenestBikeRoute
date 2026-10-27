import { SurveyTileProps } from '@/components/Tiles/Survey'
import { getSurveyData as getSurveyDataFromPrisma } from './prismaService'

export const getSurveyData = async (surveyID: string, locale?: string) => {
  try {
    const data = await getSurveyDataFromPrisma(surveyID, locale)

    if (!data) {
      return undefined
    }

    const props: SurveyTileProps = {
      title: data.title ?? '',
      answer: {
        text: data.answerText ?? '',
        percent: data.answerValue ?? 0,
        unit: data.answerUnit ?? '%',
      },
      question: data.question ?? '',
      dataSource: data.dataSource ?? '',
      dataRetrieval: data.dataRetrieval ?? new Date(),
      id: data.id ?? '',
    }
    return props
  } catch (e) {
    return undefined
  }
}
