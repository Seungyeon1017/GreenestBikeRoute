import { cx } from 'class-variance-authority'
import type { HTMLAttributes } from 'react'

export default function Card({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        'rounded-2xl border border-stone-200 bg-white p-4 shadow-sm',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function CardTitle({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cx(
        'font-lexend text-base font-bold text-stone-900',
        className,
      )}
      {...props}
    >
      {children}
    </h2>
  )
}
