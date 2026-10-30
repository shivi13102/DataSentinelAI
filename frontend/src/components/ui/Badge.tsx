// ============================================================
// Badge – severity, protection decision, and status labels
// ============================================================

import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

type BadgeVariant =
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'block'
  | 'review'
  | 'allow'
  | 'success'
  | 'info'
  | 'neutral'
  | 'warning';

interface BadgeProps {
  variant: BadgeVariant;
  children: ReactNode;
  size?: 'sm' | 'md';
  dot?: boolean;
  className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  critical: 'bg-red-950/60 text-red-400 border-red-900/50',
  high:     'bg-red-950/60 text-red-400 border-red-900/50',
  medium:   'bg-amber-950/60 text-amber-400 border-amber-900/50',
  low:      'bg-slate-800/60 text-slate-400 border-slate-700/50',
  block:    'bg-red-950/80 text-red-300 border-red-700/70',
  review:   'bg-amber-950/80 text-amber-300 border-amber-700/70',
  allow:    'bg-emerald-950/80 text-emerald-300 border-emerald-700/70',
  success:  'bg-emerald-950/60 text-emerald-400 border-emerald-900/50',
  info:     'bg-cyan-950/60 text-cyan-400 border-cyan-900/50',
  warning:  'bg-amber-950/60 text-amber-400 border-amber-900/50',
  neutral:  'bg-slate-800/60 text-slate-400 border-slate-700/50',
};

const DOT_CLASSES: Record<BadgeVariant, string> = {
  critical: 'bg-red-400',
  high:     'bg-red-400',
  medium:   'bg-amber-400',
  low:      'bg-slate-400',
  block:    'bg-red-400',
  review:   'bg-amber-400',
  allow:    'bg-emerald-400',
  success:  'bg-emerald-400',
  info:     'bg-cyan-400',
  warning:  'bg-amber-400',
  neutral:  'bg-slate-400',
};

export function Badge({
  variant,
  children,
  size = 'sm',
  dot = false,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border font-medium tracking-wide',
        size === 'sm' ? 'px-2 py-0.5 text-[11px]' : 'px-2.5 py-1 text-xs',
        VARIANT_CLASSES[variant],
        className,
      )}
    >
      {dot && (
        <span
          className={cn('h-1.5 w-1.5 shrink-0 rounded-full', DOT_CLASSES[variant])}
        />
      )}
      {children}
    </span>
  );
}

// ── Convenience wrappers ──────────────────────────────────────

export function SeverityBadge({ severity }: { severity: string }) {
  const variant = (
    severity === 'critical' ? 'critical' :
    severity === 'high'     ? 'high' :
    severity === 'medium'   ? 'medium' :
    severity === 'low'      ? 'low' : 'neutral'
  ) as BadgeVariant;

  return (
    <Badge variant={variant} dot>
      {severity.charAt(0).toUpperCase() + severity.slice(1)}
    </Badge>
  );
}

export function ProtectionBadge({ decision }: { decision: string }) {
  const variant = (
    decision === 'BLOCK'           ? 'block' :
    decision === 'REVIEW_REQUIRED' ? 'review' :
    decision === 'ALLOW'           ? 'allow' : 'neutral'
  ) as BadgeVariant;

  const label = (
    decision === 'BLOCK'           ? 'BLOCK' :
    decision === 'REVIEW_REQUIRED' ? 'REVIEW REQUIRED' :
    decision === 'ALLOW'           ? 'ALLOW' : decision
  );

  return <Badge variant={variant} size="md" dot>{label}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const lc = status.toLowerCase();
  const variant = (
    lc === 'critical' ? 'critical' :
    lc === 'warning'  ? 'warning' :
    lc === 'healthy'  ? 'success' :
    lc === 'success'  ? 'success' :
    lc === 'error'    ? 'critical' :
    lc === 'skipped'  ? 'neutral' : 'neutral'
  ) as BadgeVariant;

  return (
    <Badge variant={variant} dot>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </Badge>
  );
}

