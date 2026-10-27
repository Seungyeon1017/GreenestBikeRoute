import { Spinner } from '@/components/Elements/Spinner'

export default function MapSkeleton() {
  return (
    <div className="flex h-full w-full items-center justify-center bg-leaf-sand/50">
      <Spinner variant="light" />
    </div>
  )
}
