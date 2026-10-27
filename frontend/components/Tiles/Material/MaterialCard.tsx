import Image from 'next/image'

interface MaterialItem {
  id: string
  name: string
  description?: string
  image?: string
  fileUrl: string
}

export default function MaterialCard({
  material,
}: {
  material: MaterialItem
}) {
  return (
    <a
      className="flex gap-6 rounded-md border-l-4 border-primary bg-white p-5 transition-all hover:shadow-md"
      download
      href={material.fileUrl}
      rel="noopener noreferrer"
      target="_blank"
    >
      {material.image && (
        <Image
          alt={material.name}
          className="h-28 w-28 flex-shrink-0 rounded-sm object-cover"
          height={112}
          src={material.image}
          width={112}
        />
      )}
      <div className="flex flex-1 flex-col justify-center">
        <h4 className="text-lg font-bold text-primary">{material.name}</h4>
        {material.description && (
          <p className="mt-2 line-clamp-2 text-base leading-relaxed text-gray-700">
            {material.description}
          </p>
        )}
        <span className="mt-3 inline-flex items-center text-base font-semibold text-primary transition-colors hover:text-primary/80">
          Herunterladen
          <svg
            className="ml-2 h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path
              d="M12 5v14m0 0l-5-5m5 5l5-5M4 19h16"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
      </div>
    </a>
  )
}
