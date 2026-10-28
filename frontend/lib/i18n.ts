import 'server-only'

import { cookies } from 'next/headers'
import { defaultLocale, supportedLocales } from '@/lib/i18n/settings'

export async function getActiveLocale(): Promise<string> {
  const cookieStore = cookies()
  const cookieLang = cookieStore.get('lang')?.value

  if (cookieLang && (supportedLocales as readonly string[]).includes(cookieLang)) {
    return cookieLang
  }

  return defaultLocale
}
