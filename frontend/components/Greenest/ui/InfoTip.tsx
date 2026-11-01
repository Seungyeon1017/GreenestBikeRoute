'use client'

import { cx } from 'class-variance-authority'
import { Info } from 'lucide-react'
import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

type InfoTipProps = {
  /** Accessible name of the (i) button, e.g. "About: Dislike bumps". */
  label?: string
  /** Text to show instead of the (i), with a dashed underline, e.g. a term in a heading. */
  term?: string
  children: ReactNode
  className?: string
  /** Open the panel above the button, e.g. near the bottom of the map. */
  above?: boolean
  /** Show the panel right under the (i) instead of across the parent row, e.g. inside a scrolling list. */
  anchored?: boolean
}

const ANCHORED_WIDTH = 256
const VIEWPORT_MARGIN = 8

/**
 * (i) button with a short explanation. Opens while a mouse hovers it, and on
 * tap or click (the only way on touch screens); closes on a second tap,
 * a tap elsewhere or Escape. The panel spans its positioned parent, so give
 * the row around it `relative`.
 */
export default function InfoTip({
  label,
  term,
  children,
  className,
  above = false,
  anchored = false,
}: InfoTipProps) {
  const id = useId()
  // Opened by hover (closes when the mouse leaves) or pinned by a click/tap.
  const [hovered, setHovered] = useState(false)
  const [pinned, setPinned] = useState(false)
  const open = hovered || pinned
  const ref = useRef<HTMLSpanElement>(null)
  // Fixed position of an anchored panel, so a scrolling parent can't clip it.
  const [spot, setSpot] = useState<{
    left: number
    top?: number
    bottom?: number
  } | null>(null)

  useLayoutEffect(() => {
    if (!anchored || !open || !ref.current) {
      return
    }
    const r = ref.current.getBoundingClientRect()
    const width = Math.min(
      ANCHORED_WIDTH,
      window.innerWidth - 2 * VIEWPORT_MARGIN,
    )
    const left = Math.min(
      Math.max(r.left, VIEWPORT_MARGIN),
      window.innerWidth - width - VIEWPORT_MARGIN,
    )
    // Below the icon, or above it when the lower half of the screen is nearly used up.
    setSpot(
      r.bottom > window.innerHeight * 0.6
        ? { left, bottom: window.innerHeight - r.top }
        : { left, top: r.bottom },
    )
  }, [anchored, open])

  useEffect(() => {
    if (!anchored || !open) {
      return
    }
    const close = () => {
      setHovered(false)
      setPinned(false)
    }
    window.addEventListener('scroll', close, true)
    window.addEventListener('resize', close)
    return () => {
      window.removeEventListener('scroll', close, true)
      window.removeEventListener('resize', close)
    }
  }, [anchored, open])

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
        className={cx(
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss',
          term
            ? 'cursor-help rounded underline decoration-leaf-moss decoration-dashed decoration-2 underline-offset-[0.2em]'
            : 'rounded-full text-leaf-muted hover:text-leaf-forest',
        )}
        onClick={() => setPinned(p => !p)}
        type="button"
      >
        {term ?? <Info aria-hidden className="h-4 w-4" />}
      </button>
      {open && anchored && spot && (
        // No gap to the icon (padding instead), so the mouse can reach the panel.
        <span
          className={cx(
            'fixed z-20 block',
            spot.top === undefined ? 'pb-1' : 'pt-1',
          )}
          style={{
            ...spot,
            width: Math.min(
              ANCHORED_WIDTH,
              window.innerWidth - 2 * VIEWPORT_MARGIN,
            ),
          }}
        >
          <span
            className="block rounded-xl border border-leaf-sand bg-white p-3 font-inter text-xs font-normal leading-relaxed tracking-normal text-leaf-ink/80 shadow-soft"
            id={id}
            role="tooltip"
          >
            {children}
          </span>
        </span>
      )}
      {open && !anchored && (
        <span
          className={cx(
            'absolute inset-x-0 z-20 block rounded-xl border border-leaf-sand bg-white p-3 font-inter text-xs font-normal leading-relaxed tracking-normal text-leaf-ink/80 shadow-soft',
            above ? 'bottom-full mb-1' : 'top-full mt-1',
          )}
          id={id}
          role="tooltip"
        >
          {children}
        </span>
      )}
    </span>
  )
}
