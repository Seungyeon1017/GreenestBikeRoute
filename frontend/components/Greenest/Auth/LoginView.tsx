'use client'

import { cx } from 'class-variance-authority'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import Card from '@/components/Greenest/ui/Card'
import PageIntro from '@/components/Greenest/ui/PageIntro'
import { GreenestApiError } from '@/services/greenestApi'
import { useAuth } from './AuthProvider'

type Mode = 'login' | 'signup'

const inputClass =
  'w-full rounded-xl border border-leaf-sand bg-white px-3 py-2 text-sm text-leaf-ink focus:border-leaf-moss focus:outline-none focus:ring-2 focus:ring-leaf-moss/20'

/**
 * Where to go after logging in: the page that sent the user here (?next=/plan-trip),
 * or the profile. Only paths on this site, so a link can't send users elsewhere.
 */
function nextPath(): string {
  const next = new URLSearchParams(window.location.search).get('next')
  return next && next.startsWith('/') && !next.startsWith('//')
    ? next
    : '/profile'
}

/** Log in, or create an account and log in, then go back to where the user came from. */
export default function LoginView() {
  const { t } = useTranslation()
  const router = useRouter()
  const auth = useAuth()
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'login') {
        await auth.logIn(email, password)
      } else {
        await auth.signUp(email, password, displayName)
      }
      router.push(nextPath())
    } catch (err) {
      const status = err instanceof GreenestApiError ? err.status : undefined
      setError(
        status === 401
          ? t('greenest.auth.wrongLogin')
          : status === 409
            ? t('greenest.auth.emailTaken')
            : (err as Error).message,
      )
    } finally {
      setBusy(false)
    }
  }

  if (auth.status === 'authenticated' && auth.user) {
    return (
      <div className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-8">
        <Card className="flex flex-col gap-3">
          <p className="text-sm text-leaf-ink">
            {t('greenest.auth.alreadyIn', {
              name: auth.user.display_name ?? auth.user.email,
            })}
          </p>
          <Link
            className="self-start rounded-full bg-leaf-forest px-4 py-2 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss"
            href="/profile"
          >
            {t('greenest.auth.toProfile')}
          </Link>
        </Card>
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col gap-4 px-4 py-8">
      <PageIntro
        subtitle={t('greenest.auth.subtitle')}
        title={t(`greenest.auth.${mode}Title`)}
      />
      <Card>
        <div className="mb-4 grid grid-cols-2 gap-1 rounded-full border border-leaf-sand p-1">
          {(['login', 'signup'] as const).map(m => (
            <button
              aria-pressed={mode === m}
              className={cx(
                'rounded-full px-3 py-1.5 text-sm font-medium',
                mode === m
                  ? 'bg-leaf-forest text-leaf-cream'
                  : 'text-leaf-muted hover:bg-leaf-mint',
              )}
              key={m}
              onClick={() => {
                setMode(m)
                setError(null)
              }}
              type="button"
            >
              {t(`greenest.auth.${m}Tab`)}
            </button>
          ))}
        </div>

        <form className="flex flex-col gap-3" onSubmit={submit}>
          <label className="flex flex-col gap-1 text-xs font-medium text-leaf-muted">
            {t('greenest.auth.email')}
            <input
              autoComplete="email"
              className={inputClass}
              onChange={e => setEmail(e.target.value)}
              required
              type="email"
              value={email}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-leaf-muted">
            {t('greenest.auth.password')}
            <input
              autoComplete={
                mode === 'login' ? 'current-password' : 'new-password'
              }
              className={inputClass}
              maxLength={128}
              // The backend needs 8+ characters for new accounts; old ones log in with whatever they have.
              minLength={mode === 'signup' ? 8 : undefined}
              onChange={e => setPassword(e.target.value)}
              required
              type="password"
              value={password}
            />
          </label>
          {mode === 'signup' && (
            <label className="flex flex-col gap-1 text-xs font-medium text-leaf-muted">
              {t('greenest.auth.displayName')}
              <input
                autoComplete="nickname"
                className={inputClass}
                maxLength={100}
                onChange={e => setDisplayName(e.target.value)}
                value={displayName}
              />
            </label>
          )}

          {error && (
            <p
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-800"
              role="alert"
            >
              {error}
            </p>
          )}

          <button
            className="rounded-full bg-leaf-forest px-4 py-2.5 text-sm font-semibold text-leaf-cream hover:bg-leaf-moss disabled:opacity-60"
            disabled={busy}
            type="submit"
          >
            {busy ? t('greenest.auth.busy') : t(`greenest.auth.${mode}Submit`)}
          </button>
        </form>
      </Card>
    </div>
  )
}
