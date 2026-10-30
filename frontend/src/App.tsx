// ============================================================
// DataSentinel AI – Application root
//
// Responsibilities:
//   - Define navigation state (no React Router needed)
//   - Provide AppContext consumed by all child components
//   - Bootstrap: health check → fetch reports → load latest report
//   - Toast notification management
// ============================================================

import { createContext, useCallback, useEffect, useRef, useState } from 'react';
import './App.css';

import type { AnalysisReport, HealthResponse, ReportSummary } from './types/api';
import { checkHealth, fetchReport, fetchReports } from './lib/api';

import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import type { Toast } from './components/ui/Toast';
import { ToastContainer } from './components/ui/Toast';

import { Overview } from './pages/Overview';
import { PipelineMonitor } from './pages/PipelineMonitor';
import { DatasetAnalysis } from './pages/DatasetAnalysis';
import { AnomalyExplorer } from './pages/AnomalyExplorer';
import { AIInvestigation } from './pages/AIInvestigation';
import { Reports } from './pages/Reports';
import { SettingsPage } from './pages/Settings';

// ── Navigation type ───────────────────────────────────────────

export type Page =
  | 'overview'
  | 'pipeline'
  | 'analysis'
  | 'anomalies'
  | 'investigation'
  | 'reports'
  | 'settings';

// ── App context ───────────────────────────────────────────────

export interface AppContextValue {
  currentPage: Page;
  navigate: (page: Page) => void;
  latestReport: AnalysisReport | null;
  setLatestReport: (report: AnalysisReport) => void;
  reports: ReportSummary[];
  refreshReports: () => Promise<ReportSummary[]>;
  backendStatus: 'checking' | 'online' | 'offline';
  healthData: HealthResponse | null;
  toast: (message: string, type?: Toast['type']) => void;
}

export const AppContext = createContext<AppContextValue>({
  currentPage: 'overview',
  navigate: () => {},
  latestReport: null,
  setLatestReport: () => {},
  reports: [],
  refreshReports: async () => [],
  backendStatus: 'checking',
  healthData: null,
  toast: () => {},
});

// ── Root component ────────────────────────────────────────────

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>('overview');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [latestReport, setLatestReport] = useState<AnalysisReport | null>(null);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const bootstrapped = useRef(false);

  // ── Toast helper ────────────────────────────────────────────

  const toast = useCallback((message: string, type: Toast['type'] = 'info') => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts(prev => [...prev, { id, message, type }]);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // ── Bootstrap ────────────────────────────────────────────────

  const refreshReports = useCallback(async () => {
    try {
      const { reports: list } = await fetchReports();
      setReports(list);
      return list;
    } catch {
      return [];
    }
  }, []);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    async function bootstrap() {
      // 1. Health check
      try {
        const health = await checkHealth();
        setHealthData(health);
        setBackendStatus('online');
      } catch {
        setBackendStatus('offline');
        // Continue: still fetch local reports cache if any
      }

      // 2. Fetch report list
      let list: ReportSummary[] = [];
      try {
        const result = await fetchReports();
        list = result.reports;
        setReports(list);
      } catch {
        // No reports or backend offline
      }

      // 3. Load most recent full report (first item – API returns newest first)
      if (list.length > 0) {
        try {
          const report = await fetchReport(list[0].report_id);
          setLatestReport(report);
        } catch {
          // Could not load latest report; continue with empty state
        }
      }
    }

    void bootstrap();
  }, []);

  // ── Navigation ───────────────────────────────────────────────

  const navigate = useCallback((page: Page) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  // ── Page-level refresh ────────────────────────────────────────

  const handleRefresh = useCallback(async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      // Re-check health
      const health = await checkHealth();
      setHealthData(health);
      setBackendStatus('online');
    } catch {
      setBackendStatus('offline');
    }
    // Re-fetch reports
    const list = await refreshReports() as ReportSummary[];
    if (list.length > 0) {
      try {
        const report = await fetchReport(list[0].report_id);
        setLatestReport(report);
      } catch {}
    }
    setRefreshing(false);
    toast('Refreshed successfully', 'success');
  }, [refreshing, refreshReports, toast]);

  // ── Render ────────────────────────────────────────────────────

  const ctx: AppContextValue = {
    currentPage,
    navigate,
    latestReport,
    setLatestReport,
    reports,
    refreshReports,
    backendStatus,
    healthData,
    toast,
  };

  return (
    <AppContext.Provider value={ctx}>
      <div className="flex h-screen overflow-hidden bg-[#080D18]">
        {/* Sidebar */}
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(c => !c)}
        />

        {/* Main content */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
          <Topbar onRefresh={handleRefresh} refreshing={refreshing} />

          <main
            className="flex-1 overflow-y-auto"
            id="main-content"
          >
            <div className="animate-fade-in">
              {currentPage === 'overview'      && <Overview />}
              {currentPage === 'pipeline'      && <PipelineMonitor />}
              {currentPage === 'analysis'      && <DatasetAnalysis />}
              {currentPage === 'anomalies'     && <AnomalyExplorer />}
              {currentPage === 'investigation' && <AIInvestigation />}
              {currentPage === 'reports'       && <Reports />}
              {currentPage === 'settings'      && <SettingsPage />}
            </div>
          </main>
        </div>
      </div>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </AppContext.Provider>
  );
}
