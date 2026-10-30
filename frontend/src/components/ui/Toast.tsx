// ============================================================
// Toast notification system
// ============================================================

import { useEffect, useState } from 'react';
import { X, CheckCircle, AlertTriangle, Info } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info';
}

interface ToastItemProps {
  toast: Toast;
  onDismiss: (id: string) => void;
}

const TYPE_CONFIG = {
  success: {
    icon: CheckCircle,
    classes: 'border-emerald-900/60 bg-[#0d2218] text-emerald-300',
    iconClass: 'text-emerald-400',
  },
  error: {
    icon: AlertTriangle,
    classes: 'border-red-900/60 bg-[#1e1010] text-red-300',
    iconClass: 'text-red-400',
  },
  info: {
    icon: Info,
    classes: 'border-cyan-900/60 bg-[#0d1e2a] text-cyan-300',
    iconClass: 'text-cyan-400',
  },
};

function ToastItem({ toast, onDismiss }: ToastItemProps) {
  const [exiting, setExiting] = useState(false);
  const config = TYPE_CONFIG[toast.type];
  const Icon = config.icon;

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(() => onDismiss(toast.id), 200);
    }, 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-lg border px-4 py-3 shadow-2xl text-sm max-w-sm w-full',
        config.classes,
        exiting ? 'toast-exit' : 'toast-enter',
      )}
      role="alert"
    >
      <Icon className={cn('h-4 w-4 mt-0.5 shrink-0', config.iconClass)} />
      <p className="flex-1 leading-relaxed">{toast.message}</p>
      <button
        onClick={() => {
          setExiting(true);
          setTimeout(() => onDismiss(toast.id), 200);
        }}
        className="shrink-0 text-current opacity-60 hover:opacity-100 transition-opacity"
        aria-label="Dismiss notification"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

interface ToastContainerProps {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}

export function ToastContainer({ toasts, onDismiss }: ToastContainerProps) {
  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 items-end"
      aria-live="polite"
    >
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

