/**
 * Procurement Dashboard — shown in History > Procurement tab.
 *
 * Aggregate view across all saved procurement entries:
 * - Period selector (2W / 1M / 3M / 1Y / All)
 * - Summed metric cards (CO₂, water, land, acidification, eutrophication ×2)
 * - Per-order CO₂ trend (CSS proportional bars, newest → oldest)
 * - Order list with per-order CO₂
 */

import type { ProcurementListItem } from '../api/types';

type Period = '2w' | '1m' | '3m' | '1y' | 'all';

const PERIODS: { key: Period; label: string; days: number }[] = [
  { key: '2w',  label: '2 Weeks',  days: 14  },
  { key: '1m',  label: '1 Month',  days: 30  },
  { key: '3m',  label: '3 Months', days: 90  },
  { key: '1y',  label: '1 Year',   days: 365 },
  { key: 'all', label: 'All time', days: Infinity },
];

function filterByPeriod(entries: ProcurementListItem[], period: Period): ProcurementListItem[] {
  if (period === 'all') return entries;
  const days = PERIODS.find(p => p.key === period)!.days;
  const cutoff = Date.now() - days * 24 * 60 * 60 * 1000;
  return entries.filter(e => new Date(e.created_at).getTime() >= cutoff);
}

function fmt(v: number | null | undefined, decimals: number): string {
  return v != null ? v.toFixed(decimals) : '—';
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-NL', { day: 'numeric', month: 'short' });
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
  const filtered = filterByPeriod(entries, period);

  // Aggregate totals across filtered entries
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

  // Trend bars — sort oldest → newest for the timeline view
  const chronological = [...filtered].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
  const maxCo2 = Math.max(...chronological.map(e => e.total_co2_kg ?? 0), 1e-12);

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
        {PERIODS.map(p => (
          <button
            key={p.key}
            className={`dash-period-tab${period === p.key ? ' active' : ''}`}
            onClick={() => onPeriodChange(p.key)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <p className="stub-desc" style={{ marginTop: 16 }}>
          No orders in the selected period.
        </p>
      ) : (
        <>
          {/* Aggregate metric cards */}
          <div className="dash-metrics-grid">
            <MetricCard label="CO₂-eq"          value={totals.co2_kg}   unit="kg CO₂-eq"  decimals={3} highlight />
            <MetricCard label="Water use"         value={totals.water_m3} unit="m³"          decimals={3} />
            <MetricCard label="Land use"          value={totals.land_m2a} unit="m²·a"        decimals={3} />
            <MetricCard label="Acidification"     value={totals.so2_kg}   unit="kg SO₂-eq"  decimals={4} />
            <MetricCard label="Eutrophication FW" value={totals.p_kg}     unit="kg P-eq"    decimals={5} />
            <MetricCard label="Eutrophication Mar" value={totals.n_kg}    unit="kg N-eq"    decimals={4} />
          </div>

          {/* Summary line */}
          <div className="dash-summary">
            {filtered.length} order{filtered.length !== 1 ? 's' : ''} · {totalItems} item{totalItems !== 1 ? 's' : ''}
          </div>

          {/* CO₂ trend bars */}
          <div className="dash-trend">
            <div className="dash-trend-title">CO₂-eq per order</div>
            {chronological.map(entry => {
              const co2 = entry.total_co2_kg ?? 0;
              return (
                <div key={entry.id} className="dash-trend-row">
                  <div className="dash-trend-date">{formatDate(entry.created_at)}</div>
                  <div className="dash-trend-name" title={entry.name}>{entry.name}</div>
                  <div className="dash-trend-track">
                    <div
                      className="dash-trend-fill"
                      style={{ width: `${(co2 / maxCo2) * 100}%` }}
                    />
                  </div>
                  <div className="dash-trend-val">{fmt(co2, 3)}</div>
                </div>
              );
            })}
          </div>

          {/* Order list */}
          <div className="dash-order-list-label">All orders in period</div>
          <div className="history-list">
            {filtered.map(entry => (
              <div key={entry.id} className="history-card">
                <div className="history-card-body">
                  <div className="history-card-name">{entry.name}</div>
                  {entry.notes && (
                    <div className="history-card-notes">{entry.notes}</div>
                  )}
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
