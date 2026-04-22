import type { CSSProperties } from 'react';
import type { MealItem, MetricKey } from '../api/types';
import { toKg } from '../utils/units';
// RIVM data is per kg — scale by toKg().

const METRICS: Array<{ key: MetricKey; label: string; unit: string }> = [
  { key: 'co2_kgco2eq', label: 'CO₂-eq',      unit: 'kg' },
  { key: 'so2_kg',      label: 'Acidif.',      unit: 'kg' },
  { key: 'p_kg',        label: 'FW Eutroph.',  unit: 'kg' },
  { key: 'n_kg',        label: 'Mar. Eutroph.',unit: 'kg' },
  { key: 'land_m2a',    label: 'Land',         unit: 'm²a' },
  { key: 'water_m3',    label: 'Water',        unit: 'm³' },
];

function cellStyle(ratio: number): CSSProperties {
  if (ratio === 0) return {};
  // Map 0→white, 1→var(--green-deep) = #1A3A2A via alpha blending
  const alpha = Math.min(0.85, ratio * 0.85);
  return {
    backgroundColor: `rgba(26, 58, 42, ${alpha})`,
    color: ratio > 0.55 ? '#fff' : 'var(--text)',
  };
}

interface Props {
  items: MealItem[];
}

export default function HeatmapView({ items }: Props) {
  if (items.length === 0) return null;

  // Compute absolute totals per item per metric (scaled by amount)
  const matrix = items.map(item =>
    METRICS.map(({ key }) => {
      const val = item.variant[key];
      if (val == null) return 0;
      return val * toKg(item.amount, item.unit);
    }),
  );

  // Max per column (metric) for normalisation
  const colMax = METRICS.map((_, ci) =>
    Math.max(...matrix.map(row => row[ci]), 1e-12),
  );

  return (
    <div className="heatmap-view">
      <table className="heatmap-table" aria-label="Environmental impact heatmap">
        <thead>
          <tr>
            <th className="heatmap-th heatmap-th-ingredient">Ingredient</th>
            {METRICS.map(m => (
              <th key={m.key} className="heatmap-th">
                {m.label}
                <br />
                <span style={{ fontWeight: 400, opacity: 0.7 }}>{m.unit}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item, ri) => (
            <tr key={item.uid}>
              <td className="heatmap-name-cell" title={item.primary_name}>
                {item.primary_name}
              </td>
              {matrix[ri].map((val, ci) => {
                const ratio = val / colMax[ci];
                return (
                  <td
                    key={ci}
                    className="heatmap-cell"
                    style={cellStyle(ratio)}
                    title={`${val.toExponential(3)} ${METRICS[ci].unit}`}
                  >
                    {val === 0 ? '—' : val.toExponential(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
