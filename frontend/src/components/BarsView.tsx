import type { MealItem, MetricKey } from '../api/types';
import { toKg } from '../utils/units';
// RIVM data is per kg — scale by toKg().

interface MetricSection {
  key: MetricKey;
  label: string;
  unit: string;
  decimals: number;
}

const METRICS: MetricSection[] = [
  { key: 'co2_kgco2eq', label: 'CO₂-eq',           unit: 'kg CO₂-eq',  decimals: 4 },
  { key: 'so2_kg',      label: 'Acidification',     unit: 'kg SO₂-eq',  decimals: 5 },
  { key: 'p_kg',        label: 'FW Eutrophication', unit: 'kg P-eq',    decimals: 6 },
  { key: 'n_kg',        label: 'Mar. Eutrophication',unit: 'kg N-eq',   decimals: 5 },
  { key: 'land_m2a',    label: 'Land use',           unit: 'm²·a',       decimals: 4 },
  { key: 'water_m3',    label: 'Water use',          unit: 'm³',         decimals: 5 },
];

interface Props {
  items: MealItem[];
}

export default function BarsView({ items }: Props) {
  if (items.length === 0) return null;

  return (
    <div className="bars-view">
      {METRICS.map(m => {
        // Per-ingredient values for this metric
        const rows = items
          .map(item => ({
            uid: item.uid,
            name: item.primary_name,
            value: (item.variant[m.key] ?? 0) * toKg(item.amount, item.unit),
          }))
          .sort((a, b) => b.value - a.value);

        const max = Math.max(...rows.map(r => r.value), 1e-12);
        const total = rows.reduce((s, r) => s + r.value, 0);

        return (
          <div key={m.key} className="bars-section">
            {/* Section header */}
            <div className="bars-section-header">
              <span className="bars-section-label">{m.label}</span>
              <span className="bars-section-total">
                {total.toFixed(m.decimals)}&thinsp;{m.unit}
              </span>
            </div>

            {/* One bar per ingredient */}
            {rows.map(row => (
              <div key={row.uid} className="bar-row">
                <div className="bar-label" title={row.name}>
                  {row.name}
                </div>
                <div className="bar-track" aria-hidden="true">
                  <div
                    className="bar-fill"
                    style={{ width: `${(row.value / max) * 100}%` }}
                  />
                </div>
                <div className="bar-value">
                  {row.value.toFixed(m.decimals)}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
