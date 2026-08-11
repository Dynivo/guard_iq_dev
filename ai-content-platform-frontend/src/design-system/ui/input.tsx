import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.ComponentProps<'input'> {
  label?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, label, id, ...props }, ref) => {
    const input = (
      <input
        type={type}
        id={id}
        className={cn(
          'flex h-9 w-full rounded-[var(--radius)] border border-border bg-card px-3 py-1 text-sm shadow-soft transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        ref={ref}
        {...props}
      />
    );
    if (!label) return input;
    return (
      <div className="space-y-1.5">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        {input}
      </div>
    );
  }
);
Input.displayName = 'Input';
