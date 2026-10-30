// ============================================================
// Card – consistent panel container
// ============================================================

import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface CardProps {
  children: ReactNode;
  className?: string;
  elevated?: boolean;
  onClick?: () => void;
  role?: string;
  tabIndex?: number;
  'aria-label'?: string;
}

export function Card({
  children,
  className,
  elevated = false,
  onClick,
  role,
  tabIndex,
  'aria-label': ariaLabel,
}: CardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border',
        elevated
          ? 'bg-[#142036] border-[#223149]'
          : 'bg-[#101A2B] border-[#223149]',
        onClick && 'cursor-pointer transition-colors hover:border-[#2d4a6e]',
        className,
      )}
      onClick={onClick}
      role={role}
      tabIndex={tabIndex}
      aria-label={ariaLabel}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps {
  children: ReactNode;
  className?: string;
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between px-5 py-4 border-b border-[#223149]', className)}>
      {children}
    </div>
  );
}

interface CardTitleProps {
  children: ReactNode;
  className?: string;
}

export function CardTitle({ children, className }: CardTitleProps) {
  return (
    <h3 className={cn('text-sm font-semibold text-[#E5EDF9] tracking-wide', className)}>
      {children}
    </h3>
  );
}

interface CardBodyProps {
  children: ReactNode;
  className?: string;
}

export function CardBody({ children, className }: CardBodyProps) {
  return (
    <div className={cn('p-5', className)}>
      {children}
    </div>
  );
}

