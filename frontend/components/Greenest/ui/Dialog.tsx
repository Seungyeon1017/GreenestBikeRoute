'use client'

import { cx } from 'class-variance-authority'
import { X } from 'lucide-react'
import { type ReactNode, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

type DialogProps = {
  open: boolean
  onClose: () => void
  title: ReactNode
  /** A small line above the title, e.g. "Route von Fahrer:innen". */
  kicker?: ReactNode
  children: ReactNode
  className?: string
}

/**
 * A popup over the page: the browser's own <dialog>, so focus stays inside,
 * Esc closes it and the page behind can't be clicked. A click on the dimmed
 * backdrop closes it too. On phones it fills the width and scrolls.
 */
export default function Dialog({
  open,
  onClose,
  title,
  kicker,
  children,
  className,
}: DialogProps) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  // The content mounts only once the dialog is showing, so a map inside gets its real size.
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) {
      return
    }
    if (open && !dialog.open) {
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
    setShown(open)
  }, [open])

  return (
    <dialog
      className={cx(
        'w-[calc(100%-2rem)] max-w-2xl rounded-3xl border border-leaf-sand/80 bg-white p-0 text-leaf-ink shadow-soft backdrop:bg-leaf-ink/50',
        className,
      )}
      // Esc: let React state close it, so `open` stays in step.
      onCancel={e => {
        e.preventDefault()
        onClose()
      }}
      // The dialog element itself is only hit on the backdrop, outside the content.
      onClick={e => e.target === e.currentTarget && onClose()}
      ref={ref}
    >
      {shown && (
        <div className="flex max-h-[85vh] flex-col gap-4 overflow-y-auto p-5 md:p-6">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-0.5">
              {kicker && (
                <span className="text-[11px] font-semibold uppercase tracking-wide text-leaf-muted">
                  {kicker}
                </span>
              )}
              <h2 className="font-display text-xl font-semibold leading-snug text-leaf-forest">
                {title}
              </h2>
            </div>
            <button
              aria-label={t('greenest.dialog.close')}
              className="rounded-full p-1.5 text-leaf-muted hover:bg-leaf-mint"
              onClick={onClose}
              type="button"
            >
              <X aria-hidden className="h-5 w-5" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  )
}
