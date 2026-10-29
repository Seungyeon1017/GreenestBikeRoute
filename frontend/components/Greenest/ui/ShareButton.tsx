'use client'

import { cx } from 'class-variance-authority'
import { Check, Share2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { shareLink, type ShareResult } from '@/lib/shareLink'

type ShareButtonProps = {
  /** Builds the link when tapped (it needs window.location). */
  link: () => string
  /** Title for the share sheet. */
  title: string
  disabled?: boolean
  className?: string
}

/**
 * "Teilen": the system share sheet on phones, else copies the link. Shows the
 * link to copy by hand when neither works.
 */
export default function ShareButton({
  link,
  title,
  disabled,
  className,
}: ShareButtonProps) {
  const { t } = useTranslation()
  const [result, setResult] = useState<ShareResult | null>(null)
  const [manualUrl, setManualUrl] = useState('')

  // "Link kopiert" goes back to "Teilen" after a moment.
  useEffect(() => {
    if (result !== 'copied') {
      return
    }
    const timer = setTimeout(() => setResult(null), 2500)
    return () => clearTimeout(timer)
  }, [result])

  async function share() {
    const url = link()
    const outcome = await shareLink(url, title)
    setManualUrl(outcome === 'manual' ? url : '')
    setResult(outcome)
  }

  return (
    <div className={cx('flex flex-col gap-1.5', className)}>
      <button
        className="flex items-center justify-center gap-2 rounded-full border border-leaf-sand px-4 py-2.5 text-sm font-medium text-leaf-ink hover:bg-leaf-mint disabled:cursor-not-allowed disabled:text-leaf-muted"
        disabled={disabled}
        onClick={share}
        type="button"
      >
        {result === 'copied' ? (
          <Check aria-hidden className="h-4 w-4" />
        ) : (
          <Share2 aria-hidden className="h-4 w-4" />
        )}
        {t(
          result === 'copied'
            ? 'greenest.share.copied'
            : 'greenest.share.share',
        )}
      </button>
      {result === 'manual' && (
        <label className="flex flex-col gap-1 text-[11px] text-leaf-muted">
          {t('greenest.share.copyManually')}
          <input
            className="rounded-lg border border-leaf-sand bg-leaf-cream px-2 py-1 text-xs text-leaf-ink"
            onFocus={e => e.currentTarget.select()}
            readOnly
            value={manualUrl}
          />
        </label>
      )}
      <span aria-live="polite" className="sr-only">
        {result === 'copied' ? t('greenest.share.copied') : ''}
      </span>
    </div>
  )
}
