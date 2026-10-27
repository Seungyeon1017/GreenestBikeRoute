export const defaultLocale = 'de' as const
export const supportedLocales = ['de', 'en'] as const
export type Locale = (typeof supportedLocales)[number]
