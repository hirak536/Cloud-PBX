import { Headphones, Construction } from 'lucide-react'

export default function CallCenters() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center min-h-[60vh] text-center p-8">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-4">
        <Headphones className="h-8 w-8 text-primary" />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <Construction className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Under Development</span>
      </div>
      <h2 className="text-2xl font-bold mb-2">Call Centers</h2>
      <p className="text-muted-foreground max-w-sm">
        This feature is currently under development and will be available in a future release.
      </p>
    </div>
  )
}
