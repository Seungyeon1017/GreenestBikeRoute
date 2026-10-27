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
    <div className={cx('space-y-1', className)}>
      <h1 className="font-lexend text-2xl font-bold text-stone-900 md:text-3xl">
        {title}
      </h1>
      <p className="max-w-2xl text-sm text-stone-600 md:text-base">
        {subtitle}
      </p>
    </div>
  )
}
