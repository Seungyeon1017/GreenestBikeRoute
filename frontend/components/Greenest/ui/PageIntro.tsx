import { cx } from 'class-variance-authority'

export default function PageIntro({
  title,
  subtitle,
  className,
}: {
  title: string
  subtitle: string
  className?: string
}) {
  return (
    <div className={cx('space-y-2 pt-2 md:pt-4', className)}>
      <h1 className="font-display text-3xl font-medium tracking-tight text-leaf-forest md:text-4xl">
        {title}
      </h1>
      <p className="max-w-2xl text-sm leading-relaxed text-leaf-muted md:text-base">
        {subtitle}
      </p>
    </div>
  )
}
