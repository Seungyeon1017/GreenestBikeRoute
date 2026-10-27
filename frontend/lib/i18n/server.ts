import 'server-only'

import { createInstance, TFunction } from 'i18next'
import { getActiveLocale } from '@/lib/i18n'

import de from '@/messages/de.json'
import en from '@/messages/en.json'

const messagesMap = { de, en } as const

/**
 * Server-side translation helper. Creates a per-request i18next instance
 * using the locale from the request cookie (via getActiveLocale).
 */
export async function getT(): Promise<TFunction> {
  const locale = await getActiveLocale()
  const messages = messagesMap[locale as keyof typeof messagesMap] ?? de

  const i18n = createInstance()
  await i18n.init({
    lng: locale,
    fallbackLng: 'de',
    resources: {
      [locale]: { translation: messages },
    },
    interpolation: { escapeValue: false },
  })

  return i18n.t.bind(i18n)
}
