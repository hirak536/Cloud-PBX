import { cn } from '@/lib/utils'

export function Skeleton({ className, ...props }) {
  return (
    <div
      className={cn('rounded-lg shimmer', className)}
      {...props}
    />
  )
}
