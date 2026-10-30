// ============================================================
// Sidebar – persistent left navigation
// ============================================================

import { useContext } from 'react';
import {
  LayoutDashboard,
  GitBranch,
  Upload,
  Search,
  Brain,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { AppContext } from '../../App';
import type { Page } from '../../App';
import { cn } from '../../lib/utils';

interface NavItem {
  page: Page;
  label: string;
  icon: React.ElementType;
  description: string;
}

const NAV_ITEMS: NavItem[] = [
  { page: 'overview',      label: 'Overview',          icon: LayoutDashboard, description: 'Command centre' },
  { page: 'pipeline',      label: 'Pipeline Monitor',  icon: GitBranch,       description: 'Data flow status' },
  { page: 'analysis',      label: 'Dataset Analysis',  icon: Upload,          description: 'Upload & analyse' },
  { page: 'anomalies',     label: 'Anomaly Explorer',  icon: Search,          description: 'Investigate findings' },
  { page: 'investigation', label: 'AI Investigation',  icon: Brain,           description: 'Gemma reasoning' },
  { page: 'reports',       label: 'Reports & Audit',   icon: FileText,        description: 'Saved reports' },
  { page: 'settings',      label: 'Settings',          icon: Settings,        description: 'Configuration' },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { currentPage, navigate } = useContext(AppContext);

  return (
    <aside
      className={cn(
        'flex flex-col bg-[#0B1220] border-r border-[#223149] h-screen sticky top-0 sidebar-transition z-30',
        collapsed ? 'w-[60px]' : 'w-[220px]',
      )}
    >
      {/* Branding */}
      <div className={cn(
        'flex items-center border-b border-[#223149] shrink-0',
        collapsed ? 'px-3 py-4 justify-center' : 'px-4 py-4 gap-2.5',
      )}>
        <BrandIcon />
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-xs font-bold text-[#E5EDF9] tracking-widest leading-none">
              DATASENTINEL
            </p>
            <p className="text-[10px] text-[#22D3EE] tracking-widest font-medium mt-0.5 leading-none">
              AI
            </p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5" aria-label="Main navigation">
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          const active = currentPage === item.page;
          return (
            <button
              key={item.page}
              onClick={() => navigate(item.page)}
              title={collapsed ? `${item.label} – ${item.description}` : item.description}
              aria-label={item.label}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'w-full flex items-center rounded transition-colors focus-ring text-left',
                collapsed ? 'px-0 py-2.5 justify-center' : 'px-3 py-2.5 gap-3',
                active
                  ? 'bg-cyan-500/10 text-[#22D3EE]'
                  : 'text-[#8B9BB4] hover:text-[#E5EDF9] hover:bg-[#142036]',
              )}
            >
              <Icon
                className={cn(
                  'shrink-0',
                  collapsed ? 'h-5 w-5' : 'h-4 w-4',
                  active ? 'text-[#22D3EE]' : '',
                )}
                aria-hidden="true"
              />
              {!collapsed && (
                <span className="text-sm font-medium truncate">{item.label}</span>
              )}
              {active && !collapsed && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#22D3EE] shrink-0" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div className="shrink-0 border-t border-[#223149] p-2">
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'w-full flex items-center rounded py-2 text-[#8B9BB4] hover:text-[#E5EDF9] hover:bg-[#142036] transition-colors focus-ring',
            collapsed ? 'justify-center px-0' : 'px-3 gap-3',
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span className="text-xs">Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

function BrandIcon() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className="shrink-0"
    >
      {/* Stylised data-stream / sentinel icon */}
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#0d1e35" />
      <path d="M6 12h3M9 12 c0-2 2-4 4-4 2 0 4 2 4 4" stroke="#22D3EE" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M9 12 c0 2 2 4 4 4 2 0 4-2 4-4" stroke="#60A5FA" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="12" cy="12" r="1.5" fill="#22D3EE" />
      <path d="M17 12h1" stroke="#22D3EE" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

