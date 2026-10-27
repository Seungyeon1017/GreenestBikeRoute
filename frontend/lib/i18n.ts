import 'server-only'

import { cookies } from 'next/headers'
import { prisma } from '@/lib/prisma'

const FALLBACK_LANGUAGE = 'de'

export async function getAvailableLanguages(): Promise<string[]> {
  try {
    const options = await prisma.appOptions.findFirst()
    const languages = options?.languages?.filter(Boolean) ?? []
    return languages.length ? languages : [FALLBACK_LANGUAGE]
  } catch {
    return [FALLBACK_LANGUAGE]
  }
}

export async function getActiveLocale(): Promise<string> {
  const cookieStore = cookies()
  const cookieLang = cookieStore.get('lang')?.value
  const languages = await getAvailableLanguages()

  if (cookieLang && languages.includes(cookieLang)) {
    return cookieLang
  }

  return languages[0] || FALLBACK_LANGUAGE
}
