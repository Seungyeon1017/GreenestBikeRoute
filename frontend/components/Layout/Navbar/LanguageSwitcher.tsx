'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

const LANGUAGE_COOKIE = 'lang'
const FALLBACK_LANGUAGE = 'de'

const readCookie = (name: string) => {
  if (typeof document === 'undefined') {
    return undefined
  }
  const match = document.cookie
    .split(';')
    .map(part => part.trim())
    .find(part => part.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.split('=')[1]) : undefined
}

const setCookie = (name: string, value: string) => {
  if (typeof document === 'undefined') {
    return
  }
  const maxAge = 60 * 60 * 24 * 365
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}`
}

export default function LanguageSwitcher() {
  const router = useRouter()
  const [languages, setLanguages] = useState<string[]>([])
  const [active, setActive] = useState<string>('')

  useEffect(() => {
    const loadLanguages = async () => {
      try {
        const res = await fetch('/api/options')
        if (!res.ok) {
          return
        }
        const data = await res.json()
        const langs: string[] = data?.languages ?? []
        const normalized = langs.length ? langs : [FALLBACK_LANGUAGE]
        setLanguages(normalized)

        const cookieLang = readCookie(LANGUAGE_COOKIE)
        const nextActive =
          cookieLang && normalized.includes(cookieLang)
            ? cookieLang
            : normalized[0]
        setActive(nextActive)
      } catch {
        setLanguages([FALLBACK_LANGUAGE])
        setActive(readCookie(LANGUAGE_COOKIE) || FALLBACK_LANGUAGE)
      }
    }

    loadLanguages()
  }, [])

  const options = useMemo(() => languages.filter(Boolean), [languages])

  if (options.length <= 1) {
    return null
  }

  return (
    <div className="flex items-center gap-2">
      <label
        className="text-muted-foreground text-xs font-semibold uppercase tracking-wide"
        htmlFor="language-switcher"
      >
        lang
      </label>
      <select
        className="border-muted bg-background text-foreground rounded-md border px-2 py-1 text-sm shadow-sm"
        id="language-switcher"
        onChange={event => {
          const value = event.target.value
          setActive(value)
          setCookie(LANGUAGE_COOKIE, value)
          router.refresh()
        }}
        value={active}
      >
        {options.map(lang => (
          <option key={lang} value={lang}>
            {lang.toUpperCase()}
          </option>
        ))}
      </select>
    </div>
  )
}
