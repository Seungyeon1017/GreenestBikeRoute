'use client'

import { cx } from 'class-variance-authority'
import { Info } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type InfoTipProps = {
  /** Accessible name of the (i) button, e.g. "About: Dislike bumps". */
  label: string
  children: ReactNode
  className?: string
}

/**
 * (i) button with a short explanation. Opens while a mouse hovers it, and on
 * tap or click (the only way on touch screens); closes on a second tap,
 * a tap elsewhere or Escape. The panel spans its positioned parent, so give
 * the row around it `relative`.
 */
export default function InfoTip({ label, children, className }: InfoTipProps) {
  const id = useId()
  // Opened by hover (closes when the mouse leaves) or pinned by a click/tap.
  const [hovered, setHovered] = useState(false)
  const [pinned, setPinned] = useState(false)
  const open = hovered || pinned
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!pinned) {
      return
    }
    const close = (e: PointerEvent | KeyboardEvent) => {
      if (
        e instanceof KeyboardEvent
          ? e.key === 'Escape'
          : !ref.current?.contains(e.target as Node)
      ) {
        setPinned(false)
      }
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
    }
  }, [pinned])

  return (
    <span
      className={cx('inline-flex', className)}
      // Hover only for a real mouse: a tap also fires pointerenter, which would open and close at once.
      onPointerEnter={e => e.pointerType === 'mouse' && setHovered(true)}
      onPointerLeave={e => e.pointerType === 'mouse' && setHovered(false)}
      ref={ref}
    >
      <button
        aria-controls={id}
        aria-expanded={open}
        aria-label={label}
        className="rounded-full text-leaf-muted hover:text-leaf-forest focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss"
        onClick={() => setPinned(p => !p)}
        type="button"
      >
        <Info aria-hidden className="h-4 w-4" />
      </button>
      {open && (
        <span
          className="absolute inset-x-0 top-full z-20 mt-1 block rounded-xl border border-leaf-sand bg-white p-3 text-xs font-normal leading-relaxed text-leaf-ink/80 shadow-soft"
          id={id}
          role="tooltip"
        >
          {children}
        </span>
      )}
    </span>
  )
}
