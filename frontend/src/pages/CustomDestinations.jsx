import { Bookmark, Clock } from 'lucide-react'

export default function CustomDestinations() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-500/10">
        <Bookmark className="h-8 w-8 text-indigo-500" />
      </div>
      <div>
        <h1 className="text-2xl font-bold">Custom Destinations</h1>
        <p className="mt-1 text-muted-foreground flex items-center justify-center gap-1.5">
          <Clock className="h-4 w-4" /> Coming Soon
        </p>
      </div>
      <p className="max-w-sm text-sm text-muted-foreground">
        Define reusable named destination presets that can be referenced from DIDs, Working Hours, Ring Groups, and anywhere else a destination is needed.
      </p>
    </div>
  )
}
