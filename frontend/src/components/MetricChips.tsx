import type { MealItem, MetricKey } from '../api/types';
import { toKg } from '../utils/units';
// RIVM LCA data is expressed per kg of product, so we scale by toKg().

interface MetricDef {
  key: MetricKey;
  label: string;
  unit: string;
  decimals: number;
}

const METRICS: MetricDef[] = [
  { key: 'co2_kgco2eq', label: 'CO₂-eq',        unit: 'kg',        decimals: 3 },
  { key: 'so2_kg',      label: 'Acidif.',         unit: 'kg SO₂-eq', decimals: 4 },
  { key: 'p_kg',        label: 'FW Eutroph.',     unit: 'kg P-eq',   decimals: 5 },
  { key: 'n_kg',        label: 'Mar. Eutroph.',   unit: 'kg N-eq',   decimals: 4 },
  { key: 'land_m2a',    label: 'Land',            unit: 'm²·a',      decimals: 3 },
  { key: 'water_m3',    label: 'Water',           unit: 'm³',        decimals: 4 },
];

interface Props {
  items: MealItem[];
}

export default function MetricChips({ items }: Props) {
  return (
    <div className="metric-chips">
      {METRICS.map(m => {
        const total = items.reduce((sum, item) => {
          const val = item.variant[m.key];
          if (val == null) return sum;
          return sum + val * toKg(item.amount, item.unit);
        }, 0);

        return (
          <div key={m.key} className="metric-chip">
            <span className="metric-chip-value">{total.toFixed(m.decimals)}</span>
            <span className="metric-chip-label">
              {m.label}
              <br />
              <span style={{ opacity: 0.7, fontWeight: 400 }}>{m.unit}</span>
            </span>
          </div>
        );
      })}
    </div>
  );
}
