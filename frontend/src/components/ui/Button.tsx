// ============================================================
// Button – primary action component
// ============================================================

import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: ReactNode;
  children?: ReactNode;
}

const VARIANT_CLASSES = {
  primary:   'bg-cyan-500 text-slate-900 hover:bg-cyan-400 font-semibold',
  secondary: 'bg-[#142036] text-[#E5EDF9] border border-[#223149] hover:bg-[#1a2d4a] hover:border-[#2d4a6e]',
  ghost:     'text-[#8B9BB4] hover:text-[#E5EDF9] hover:bg-[#101A2B]',
  danger:    'bg-red-900/40 text-red-400 border border-red-900/60 hover:bg-red-900/60',
};

const SIZE_CLASSES = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2   text-sm gap-2',
  lg: 'px-5 py-2.5 text-sm gap-2',
};

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded transition-colors focus-ring',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        VARIANT_CLASSES[variant],
        SIZE_CLASSES[size],
        className,
      )}
      disabled={disabled ?? loading}
      {...props}
    >
      {loading ? (
        <svg
          className="h-3.5 w-3.5 animate-spin"
          viewBox="0 0 24 24"
          fill="none"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      ) : icon ? (
        <span className="shrink-0" aria-hidden="true">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}

