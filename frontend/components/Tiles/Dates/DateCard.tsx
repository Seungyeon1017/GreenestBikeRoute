import Image from 'next/image'

interface DateEvent {
  id: string
  title: string
  description?: string
  startDate?: string
  endDate?: string
  image?: string
  link?: string
}

function formatDateRange(startDate?: string, endDate?: string): string {
  const dateOpts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }
  const timeOpts: Intl.DateTimeFormatOptions = {
    hour: '2-digit',
    minute: '2-digit',
  }

  const start = startDate ? new Date(startDate) : null
  const end = endDate ? new Date(endDate) : null

  const fmtDate = (d: Date) => d.toLocaleDateString('de-DE', dateOpts)
  const fmtTime = (d: Date) => d.toLocaleTimeString('de-DE', timeOpts)

  if (start && end) {
    if (fmtDate(start) === fmtDate(end)) {
      return `${fmtDate(start)}, ${fmtTime(start)} – ${fmtTime(end)} Uhr`
    }
    return `${fmtDate(start)}, ${fmtTime(start)} – ${fmtDate(end)}, ${fmtTime(end)} Uhr`
  }

  if (start) {
    return `${fmtDate(start)}, ${fmtTime(start)} Uhr`
  }

  if (end) {
    return `${fmtDate(end)}, ${fmtTime(end)} Uhr`
  }

  return ''
}

export default function DateCard({ event }: { event: DateEvent }) {
  return (
    <div className="flex gap-6 rounded-md border-l-4 border-climate bg-white p-5 transition-all hover:shadow-md">
      {event.image && (
        <Image
          alt={event.title}
          className="h-28 w-28 flex-shrink-0 rounded-sm object-cover"
          height={112}
          src={event.image}
          width={112}
        />
      )}
      <div className="flex-1">
        <div className="text-sm font-semibold uppercase tracking-wide text-climate">
          {formatDateRange(event.startDate, event.endDate)}
        </div>
        <h4 className="mt-1 text-lg font-bold text-primary">{event.title}</h4>
        {event.description && (
          <p className="mt-2 line-clamp-2 text-base leading-relaxed text-gray-700">
            {event.description}
          </p>
        )}
        {event.link && (
          <a
            className="mt-3 inline-flex items-center text-base font-semibold text-climate transition-colors hover:text-climate-light"
            href={event.link}
            rel="noopener noreferrer"
            target="_blank"
          >
            Mehr erfahren und Anmeldung
            <span className="ml-1">→</span>
          </a>
        )}
      </div>
    </div>
  )
}
