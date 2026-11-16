'use client'

import { cx } from 'class-variance-authority'

type SegmentedProps<T extends string> = {
  /** Accessible name of the group, e.g. "Departure". */
  label: string
  options: { value: T; label: string }[]
  value: T
  onChange: (_value: T) => void
  disabled?: boolean
  id?: string
  className?: string
}

/** A switch of two or three parts side by side, one of them chosen (a radio group). */
export default function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  disabled = false,
  id,
  className,
}: SegmentedProps<T>) {
  return (
    <div
      aria-label={label}
      className={cx(
        'flex rounded-lg border border-leaf-sand bg-leaf-cream/60 p-0.5',
        disabled && 'opacity-50',
        className,
      )}
      id={id}
      role="radiogroup"
    >
      {options.map(option => {
        const chosen = option.value === value
        return (
          <button
            aria-checked={chosen}
            className={cx(
              'min-w-0 flex-1 rounded-md px-2 py-1 text-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-moss',
              chosen
                ? 'bg-white font-medium text-leaf-forest shadow-sm'
                : 'text-leaf-ink/70',
              !chosen && !disabled && 'hover:text-leaf-ink',
              disabled && 'cursor-not-allowed',
            )}
            disabled={disabled}
            key={option.value}
            onClick={() => !chosen && onChange(option.value)}
            role="radio"
            type="button"
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
