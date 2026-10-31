import { cx } from 'class-variance-authority'
import InfoTip from '@/components/Greenest/ui/InfoTip'

export default function PageIntro({
  title,
  subtitle,
  note,
  className,
}: {
  title: string
  subtitle: string
  /** Explains `term`, a word in the title, in a tooltip on that word. */
  note?: { term: string; text: string }
  className?: string
}) {
  const termAt = note ? title.indexOf(note.term) : -1
  return (
    <div className={cx('space-y-2 pt-2 md:pt-4', className)}>
      <h1 className="relative max-w-2xl font-display text-3xl font-medium tracking-tight text-leaf-forest md:text-4xl">
        {note && termAt >= 0 ? (
          <>
            {title.slice(0, termAt)}
            <InfoTip term={note.term}>{note.text}</InfoTip>
            {title.slice(termAt + note.term.length)}
          </>
        ) : (
          title
        )}
      </h1>
      <p className="max-w-2xl text-sm leading-relaxed text-leaf-muted md:text-base">
        {subtitle}
      </p>
    </div>
  )
}
