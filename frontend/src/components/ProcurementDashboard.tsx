/**
 * Procurement Dashboard — shown in History > Procurement tab.
 *
 * Aggregate view across saved procurement entries:
 * - Period selector (2W / 1M / 3M / 1Y / All / Custom date range)
 * - Summed metric cards (CO₂, water, land, acidification, eutrophication ×2)
 * - Order list with per-order CO₂ and open/delete actions
 */

import { useState } from 'react';
import type { ProcurementListItem } from '../api/types';

type Period = '2w' | '1m' | '3m' | '1y' | 'all' | 'custom';

const QUICK_PERIODS: { key: Period; label: string; days: number }[] = [
  { key: '2w',  label: '2 Weeks',  days: 14  },
  { key: '1m',  label: '1 Month',  days: 30  },
  { key: '3m',  label: '3 Months', days: 90  },
  { key: '1y',  label: '1 Year',   days: 365 },
  { key: 'all', label: 'All time', days: Infinity },
];

function filterByPeriod(
  entries: ProcurementListItem[],
  period: Period,
  customFrom: string,
  customTo: string,
): ProcurementListItem[] {
  if (period === 'custom') {
    const from = customFrom ? new Date(customFrom).getTime() : 0;
    // custom "to" is end-of-day
    const to   = customTo   ? new Date(customTo).getTime() + 86400000 : Infinity;
    return entries.filter(e => {
      const t = new Date(e.created_at).getTime();
      return t >= from && t <= to;
    });
  }
  if (period === 'all') return entries;
  const days   = QUICK_PERIODS.find(p => p.key === period)!.days;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return entries.filter(e => new Date(e.created_at).getTime() >= cutoff);
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-NL', { day: 'numeric', month: 'short', year: 'numeric' });
}

interface MetricCardProps {
  label: string;
  value: number;
  unit: string;
  decimals: number;
  highlight?: boolean;
}

function MetricCard({ label, value, unit, decimals, highlight }: MetricCardProps) {
  return (
    <div className={`dash-metric-card${highlight ? ' dash-metric-card--co2' : ''}`}>
      <div className="dash-metric-value">{value.toFixed(decimals)}</div>
      <div className="dash-metric-unit">{unit}</div>
      <div className="dash-metric-label">{label}</div>
    </div>
  );
}

interface Props {
  entries: ProcurementListItem[];
  period: Period;
  onPeriodChange: (p: Period) => void;
  busy: boolean;
  onOpen: (entry: ProcurementListItem) => void;
  onDelete: (entry: ProcurementListItem) => void;
  openingId: string | null;
  deletingId: string | null;
  onGoToProcurement: () => void;
}

export default function ProcurementDashboard({
  entries,
  period,
  onPeriodChange,
  busy,
  onOpen,
  onDelete,
  openingId,
  deletingId,
  onGoToProcurement,
}: Props) {
  const [customFrom, setCustomFrom] = useState('');
  const [customTo,   setCustomTo]   = useState('');

  const filtered = filterByPeriod(entries, period, customFrom, customTo);

  // Aggregate totals
  const totals = filtered.reduce(
    (acc, e) => ({
      co2_kg:   acc.co2_kg   + (e.total_co2_kg   ?? 0),
      water_m3: acc.water_m3 + (e.total_water_m3 ?? 0),
      land_m2a: acc.land_m2a + (e.total_land_m2a ?? 0),
      so2_kg:   acc.so2_kg   + (e.total_so2_kg   ?? 0),
      p_kg:     acc.p_kg     + (e.total_p_kg     ?? 0),
      n_kg:     acc.n_kg     + (e.total_n_kg     ?? 0),
    }),
    { co2_kg: 0, water_m3: 0, land_m2a: 0, so2_kg: 0, p_kg: 0, n_kg: 0 },
  );

  const totalItems = filtered.reduce((s, e) => s + e.item_count, 0);

  if (entries.length === 0) {
    return (
      <div className="stub-card" style={{ marginTop: 24 }}>
        <h2 className="stub-title">No saved orders yet</h2>
        <p className="stub-desc">
          Add products in Procurement mode and click <strong>Save order</strong> to keep them here.
        </p>
        <button className="btn-primary" style={{ marginTop: '16px' }} onClick={onGoToProcurement}>
          Go to Procurement mode →
        </button>
      </div>
    );
  }

  return (
    <div className="procurement-dashboard">
      {/* Period selector */}
      <div className="dash-period-tabs">
        {QUICK_PERIODS.map(p => (
          <button
            key={p.key}
            className={`dash-period-tab${period === p.key ? ' active' : ''}`}
            onClick={() => onPeriodChange(p.key)}
          >
            {p.label}
          </button>
        ))}
        <button
          className={`dash-period-tab${period === 'custom' ? ' active' : ''}`}
          onClick={() => onPeriodChange('custom')}
        >
          Custom
        </button>
      </div>

      {/* Custom date range inputs */}
      {period === 'custom' && (
        <div className="dash-custom-range">
          <label className="dash-custom-label">From</label>
          <input
            type="date"
            className="dash-date-input"
            value={customFrom}
            onChange={e => setCustomFrom(e.target.value)}
          />
          <label className="dash-custom-label">To</label>
          <input
            type="date"
            className="dash-date-input"
            value={customTo}
            onChange={e => setCustomTo(e.target.value)}
          />
        </div>
      )}

      {filtered.length === 0 ? (
        <p className="stub-desc" style={{ marginTop: 16 }}>
          No orders in the selected period.
        </p>
      ) : (
        <>
          {/* Aggregate metric cards */}
          <div className="dash-metrics-grid">
            <MetricCard label="CO₂-eq"             value={totals.co2_kg}   unit="kg CO₂-eq"  decimals={3} highlight />
            <MetricCard label="Water use"           value={totals.water_m3} unit="m³"          decimals={3} />
            <MetricCard label="Land use"            value={totals.land_m2a} unit="m²·a"        decimals={3} />
            <MetricCard label="Acidification"       value={totals.so2_kg}   unit="kg SO₂-eq"  decimals={4} />
            <MetricCard label="Eutrophication FW"   value={totals.p_kg}     unit="kg P-eq"    decimals={5} />
            <MetricCard label="Eutrophication Mar." value={totals.n_kg}     unit="kg N-eq"    decimals={4} />
          </div>

          <div className="dash-summary">
            {filtered.length} order{filtered.length !== 1 ? 's' : ''} · {totalItems} item{totalItems !== 1 ? 's' : ''}
          </div>

          {/* Order list */}
          <div className="history-list">
            {filtered.map(entry => (
              <div key={entry.id} className="history-card">
                <div className="history-card-body">
                  <div className="history-card-name">{entry.name}</div>
                  {entry.notes && <div className="history-card-notes">{entry.notes}</div>}
                  <div className="history-card-meta">
                    <span>{formatDate(entry.created_at)}</span>
                    <span className="history-card-sep">·</span>
                    <span>{entry.item_count} item{entry.item_count !== 1 ? 's' : ''}</span>
                    {entry.total_co2_kg != null && (
                      <>
                        <span className="history-card-sep">·</span>
                        <span className="history-card-co2">
                          {entry.total_co2_kg.toFixed(3)} kg CO₂
                        </span>
                      </>
                    )}
                  </div>
                </div>
                <div className="history-card-actions">
                  <button
                    className="btn-history-open"
                    onClick={() => onOpen(entry)}
                    disabled={busy}
                    aria-label={`Open ${entry.name}`}
                  >
                    {openingId === entry.id ? 'Loading…' : 'Open →'}
                  </button>
                  <button
                    className="btn-ghost history-delete"
                    onClick={() => onDelete(entry)}
                    disabled={busy}
                    aria-label={`Delete ${entry.name}`}
                  >
                    {deletingId === entry.id ? '…' : '✕'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
