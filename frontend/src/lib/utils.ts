// ============================================================
// DataSentinel AI – Utility helpers
// ============================================================

import type { Finding } from '../types/api';

// ── Health Score ─────────────────────────────────────────────
//
// Frontend-derived indicator. Formula:
//   Start at 100.
//   Subtract: critical=40, high=20, medium=10, low=3 per finding.
//   Clamp to [0, 100].
//
// This is a transparency-first UX metric, not a statistical
// probability of data correctness.

const SEVERITY_PENALTY: Record<string, number> = {
  critical: 40,
  high: 20,
  medium: 10,
  low: 3,
};

export function calculateHealthScore(findings: Finding[]): number {
  let penalty = 0;
  for (const f of findings) {
    penalty += SEVERITY_PENALTY[f.severity] ?? 0;
  }
  return Math.max(0, Math.min(100, 100 - penalty));
}

// ── Number formatting ─────────────────────────────────────────

export function formatNumber(value: number, decimals = 2): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatPercent(value: number, decimals = 2): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Format a p-value. Values rounded to exactly 0 by the backend
 * are labelled as "< reported precision" rather than "0.000000"
 * to avoid implying the true p-value is exactly zero.
 */
export function formatPValue(value: number): string {
  if (value === 0) return '< reported precision';
  if (value < 0.0001) return value.toExponential(2);
  return value.toFixed(6);
}

// ── Timestamp formatting ──────────────────────────────────────

export function formatTimestamp(iso: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
      timeZone: 'UTC',
      timeZoneName: 'short',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatRelativeTime(iso: string): string {
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return '';
  }
}

// ── Label helpers ─────────────────────────────────────────────

export function getFindingTypeLabel(type: string): string {
  const LABELS: Record<string, string> = {
    missing_value_anomaly: 'Missing Values',
    duplicate_anomaly: 'Duplicate Rows',
    distribution_drift: 'Distribution Drift',
    categorical_drift: 'Categorical Drift',
    schema_change: 'Schema Change',
  };
  return LABELS[type] ?? type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

export function getSeverityLabel(severity: string): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1).toLowerCase();
}

export function getStatusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}

// ── File download ─────────────────────────────────────────────

export function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Class merging ─────────────────────────────────────────────

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ');
}

