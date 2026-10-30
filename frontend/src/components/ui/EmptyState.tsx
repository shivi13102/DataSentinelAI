// ============================================================
// EmptyState – placeholder when there is no data to display
// ============================================================

import type { ReactNode } from 'react';
import { cn } from '../../lib/utils';

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 py-16 px-8 text-center',
        className,
      )}
    >
      {icon && (
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#142036] text-[#8B9BB4]">
          {icon}
        </div>
      )}
      <div className="space-y-1">
        <p className="text-sm font-medium text-[#E5EDF9]">{title}</p>
        {description && (
          <p className="text-xs text-[#8B9BB4] max-w-xs">{description}</p>
        )}
      </div>
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

