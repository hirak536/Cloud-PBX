/**
 * CheckRow — a labelled checkbox row used in form settings.
 * Props:
 *   checked   - boolean
 *   onChange  - (checked: boolean) => void
 *   label     - string
 *   className - optional extra classes
 */
export default function CheckRow({ checked, onChange, label, className = '' }) {
  return (
    <label className={`flex items-center gap-2.5 py-1 cursor-pointer select-none group ${className}`}>
      <input
        type="checkbox"
        checked={checked}
        onChange={e => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-input accent-primary cursor-pointer"
      />
      <span className="text-sm group-hover:text-foreground text-muted-foreground transition-colors">
        {label}
      </span>
    </label>
  )
}
