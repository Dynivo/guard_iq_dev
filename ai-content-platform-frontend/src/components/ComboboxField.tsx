import { useMemo, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ComboboxFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  placeholder?: string;
  hint?: string;
  className?: string;
}

/** Type freely or pick from suggestions — easy for non-technical clients. */
export function ComboboxField({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  hint,
  className,
}: ComboboxFieldProps) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    const q = value.trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => o.toLowerCase().includes(q));
  }, [options, value]);

  return (
    <div className={cn('relative space-y-1.5', className)} ref={wrapRef}>
      <label htmlFor={id} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type="text"
          value={value}
          placeholder={placeholder}
          autoComplete="off"
          onChange={(e) => {
            onChange(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => {
            // Allow click on option before closing
            window.setTimeout(() => setOpen(false), 150);
          }}
          className={cn(
            'flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 pr-9 text-sm',
            'placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
          )}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-list`}
        />
        <button
          type="button"
          tabIndex={-1}
          className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground hover:text-foreground"
          aria-label="Show options"
          onMouseDown={(e) => {
            e.preventDefault();
            setOpen((v) => !v);
          }}
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>
      {open && filtered.length > 0 && (
        <ul
          id={`${id}-list`}
          role="listbox"
          className="absolute z-20 mt-1 max-h-48 w-full overflow-auto rounded-md border border-border bg-card py-1 shadow-elevated"
        >
          {filtered.map((opt) => (
            <li key={opt} role="option">
              <button
                type="button"
                className={cn(
                  'w-full px-3 py-2 text-left text-sm transition-colors hover:bg-hover',
                  opt === value && 'bg-accent/10 font-medium text-foreground'
                )}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(opt);
                  setOpen(false);
                }}
              >
                {opt}
              </button>
            </li>
          ))}
        </ul>
      )}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
