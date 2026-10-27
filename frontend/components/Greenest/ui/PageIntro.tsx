import { cx } from 'class-variance-authority'

export default function PageIntro({
  eyebrow,
  title,
  subtitle,
  className,
}: {
  eyebrow?: string
  title: string
  subtitle: string
  className?: string
}) {
  return (
    <div className={cx('space-y-2 pt-2 md:pt-4', className)}>
      {eyebrow && (
        <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-leaf-fern">
          {eyebrow}
        </p>
      )}
      <h1 className="font-display text-3xl font-medium tracking-tight text-leaf-forest md:text-4xl">
        {title}
      </h1>
      <p className="max-w-2xl text-sm leading-relaxed text-leaf-muted md:text-base">
        {subtitle}
      </p>
    </div>
  )
}
