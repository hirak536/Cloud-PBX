import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-semibold transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 select-none active:scale-[0.97]',
  {
    variants: {
      variant: {
        default:     'bg-primary text-primary-foreground shadow-sm shadow-primary/30 hover:bg-primary/90 hover:shadow-md hover:shadow-primary/25 hover:-translate-y-px',
        destructive: 'bg-destructive text-destructive-foreground shadow-sm shadow-destructive/30 hover:bg-destructive/90 hover:shadow-md hover:-translate-y-px',
        outline:     'border border-input bg-background/80 hover:bg-accent hover:text-accent-foreground hover:-translate-y-px',
        secondary:   'bg-secondary text-secondary-foreground hover:bg-secondary/70 hover:-translate-y-px',
        ghost:       'hover:bg-accent hover:text-accent-foreground',
        link:        'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm:      'h-8 rounded-md px-3 text-xs',
        lg:      'h-10 rounded-lg px-6',
        icon:    'h-9 w-9',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  }
)

export function Button({ className, variant, size, ...props }) {
  return (
    <button
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
