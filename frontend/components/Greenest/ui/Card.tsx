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
        'rounded-3xl border border-leaf-sand/80 bg-white p-5 shadow-soft',
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
        'font-display text-lg font-semibold tracking-tight text-leaf-forest',
        className,
      )}
      {...props}
    >
      {children}
    </h2>
  )
}
