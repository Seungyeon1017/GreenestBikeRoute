'use client'

import { createInstance } from 'i18next'
import { I18nextProvider, initReactI18next } from 'react-i18next'
import { useMemo } from 'react'

interface TranslationsProviderProps {
  locale: string
  messages: Record<string, unknown>
  children: React.ReactNode
}

export default function TranslationsProvider({
  locale,
  messages,
  children,
}: TranslationsProviderProps) {
  const i18n = useMemo(() => {
    const instance = createInstance()
    instance.use(initReactI18next).init({
      lng: locale,
      fallbackLng: 'de',
      resources: {
        [locale]: { translation: messages },
      },
      interpolation: { escapeValue: false },
    })
    return instance
  // locale changes trigger a full page reload via LanguageSwitcher, so
  // memoising on locale is sufficient and avoids unnecessary re-inits.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locale])

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
}
