import { DayPicker } from 'react-day-picker'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight } from 'lucide-react'

export function Calendar({ className, classNames, showOutsideDays = true, ...props }) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      navLayout="around"
      className={cn('p-3 w-max', className)}
      classNames={{
        months: 'flex flex-col sm:flex-row gap-5',
        month: 'relative w-56 space-y-3',
        month_caption: 'flex h-8 items-center justify-center px-8',
        caption_label: 'text-sm font-semibold',
        nav: 'contents',
        button_previous: cn(
          'absolute left-0 top-0 h-8 w-8 bg-transparent p-0 text-muted-foreground hover:text-foreground',
          'inline-flex items-center justify-center rounded-md hover:bg-accent transition-colors'
        ),
        button_next: cn(
          'absolute right-0 top-0 h-8 w-8 bg-transparent p-0 text-muted-foreground hover:text-foreground',
          'inline-flex items-center justify-center rounded-md hover:bg-accent transition-colors'
        ),
        month_grid: 'w-full table-fixed border-collapse',
        weekdays: '',
        weekday: 'h-8 w-8 text-center text-[0.78rem] font-semibold text-muted-foreground',
        week: '',
        day: 'relative h-8 w-8 p-0 text-center text-sm focus-within:relative focus-within:z-20',
        day_button: cn(
          'h-8 w-8 p-0 font-normal rounded-md hover:bg-accent hover:text-accent-foreground',
          'inline-flex items-center justify-center transition-colors aria-selected:opacity-100'
        ),
        selected: 'bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground rounded-md',
        today: 'bg-accent text-accent-foreground font-semibold',
        outside: 'text-muted-foreground opacity-50',
        disabled: 'text-muted-foreground opacity-50 pointer-events-none',
        range_start: 'rounded-l-md bg-primary text-primary-foreground',
        range_end: 'rounded-r-md bg-primary text-primary-foreground',
        range_middle: 'bg-accent text-accent-foreground rounded-none',
        hidden: 'invisible',
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === 'left'
            ? <ChevronLeft className="h-4 w-4" />
            : <ChevronRight className="h-4 w-4" />,
      }}
      {...props}
    />
  )
}
