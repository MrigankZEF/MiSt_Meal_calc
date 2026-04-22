import type { MealItem, MetricKey } from '../api/types';
import { toKg } from '../utils/units';
// RIVM data is per kg — scale by toKg().

// ── Per-axis reference values ─────────────────────────────────────────────
//
// Derived from the actual RIVM reference.db using the 95th-percentile
// value per metric across all products (rounded up slightly).
// Each axis is normalised as:  norm = meal_total / (REFERENCE × meal_kg)
// so 1.0 = "as impactful per kg as a 95th-percentile product in this category."
// Values above 1.0 are clamped.  Low-impact ingredients score near 0.
//
// Metric           p95 in DB   Reference used
// co2_kgco2eq      13.84 /kg   14 kg CO₂-eq/kg
// so2_kg           0.052 /kg   0.053 kg SO₂-eq/kg
// p_kg             0.00524/kg  0.0053 kg P-eq/kg
// n_kg             0.0162 /kg  0.017 kg N-eq/kg
// land_m2a         11.97  /kg  12 m²a/kg
// water_m3         0.348  /kg  0.35 m³/kg

const AXIS_REFS: Record<MetricKey, number> = {
  co2_kgco2eq: 14.0,
  so2_kg:       0.053,
  p_kg:         0.0053,
  n_kg:         0.017,
  land_m2a:    12.0,
  water_m3:     0.35,
};

// ── Axes ──────────────────────────────────────────────────────────────────

const AXES: Array<{ key: MetricKey; label: string }> = [
  { key: 'co2_kgco2eq', label: 'CO₂-eq' },
  { key: 'so2_kg',      label: 'Acidif.' },
  { key: 'p_kg',        label: 'FW\nEutroph.' },
  { key: 'n_kg',        label: 'Mar.\nEutroph.' },
  { key: 'land_m2a',    label: 'Land' },
  { key: 'water_m3',    label: 'Water' },
];

const N = AXES.length; // 6

// ── SVG geometry ──────────────────────────────────────────────────────────

const SIZE    = 280;
const CX      = SIZE / 2;
const CY      = SIZE / 2;
const R       = 96;   // outer ring radius
const LABEL_R = R + 26;

function axisAngle(i: number): number {
  // Start at top (−π/2), step clockwise
  return (i / N) * 2 * Math.PI - Math.PI / 2;
}

function polarPoint(r: number, i: number): [number, number] {
  const a = axisAngle(i);
  return [CX + r * Math.cos(a), CY + r * Math.sin(a)];
}

function pointsStr(r: number): string {
  return Array.from({ length: N }, (_, i) => polarPoint(r, i).join(',')).join(' ');
}

// ── Component ─────────────────────────────────────────────────────────────

interface Props {
  items: MealItem[];
}

export default function RadarView({ items }: Props) {
  if (items.length === 0) return null;

  // Total meal weight (kg) for normalisation denominator
  const totalKg = items.reduce((s, item) => s + toKg(item.amount, item.unit), 0);

  // Absolute totals per axis across all meal items
  const totals = AXES.map(({ key }) =>
    items.reduce((sum, item) => {
      const val = item.variant[key];
      if (val == null) return sum;
      return sum + val * toKg(item.amount, item.unit);
    }, 0),
  );

  // Normalise: fraction of "worst-case" reference for this meal weight, capped at 1
  const norm = totals.map((t, i) => {
    const ref = AXIS_REFS[AXES[i].key] * totalKg;
    return ref > 0 ? Math.min(1, t / ref) : 0;
  });

  // Data polygon — scale to SVG radius
  const dataPoints = norm
    .map((v, i) => polarPoint(R * Math.max(0.04, v), i).join(',')) // min dot size
    .join(' ');

  const gridRings = [0.25, 0.5, 0.75, 1.0];

  return (
    <div className="radar-view">
      <svg
        width={SIZE}
        height={SIZE}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        aria-label="Radar chart showing 6 environmental metrics"
        role="img"
      >
        {/* Grid rings */}
        {gridRings.map(f => (
          <polygon
            key={f}
            points={pointsStr(R * f)}
            fill="none"
            stroke="var(--border)"
            strokeWidth={f === 1 ? 1.2 : 0.7}
          />
        ))}

        {/* Axis spokes */}
        {AXES.map((_, i) => {
          const [x, y] = polarPoint(R, i);
          return (
            <line
              key={i}
              x1={CX} y1={CY}
              x2={x}  y2={y}
              stroke="var(--border)"
              strokeWidth={0.8}
            />
          );
        })}

        {/* Grid ring % labels (25 / 50 / 75) on top-right spoke */}
        {[0.25, 0.5, 0.75].map(f => {
          const [lx, ly] = polarPoint(R * f, 0); // top spoke
          return (
            <text
              key={f}
              x={lx + 4}
              y={ly}
              fontSize={8}
              fill="var(--hint)"
              fontFamily="DM Sans, sans-serif"
              dominantBaseline="middle"
            >
              {Math.round(f * 100)}%
            </text>
          );
        })}

        {/* Data polygon */}
        <polygon
          points={dataPoints}
          fill="rgba(82, 183, 136, 0.22)"
          stroke="var(--green-bright)"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Axis labels */}
        {AXES.map(({ label }, i) => {
          const [lx, ly] = polarPoint(LABEL_R, i);
          const anchor = lx < CX - 4 ? 'end' : lx > CX + 4 ? 'start' : 'middle';
          const lines = label.split('\n');
          return (
            <text
              key={i}
              x={lx}
              y={ly}
              textAnchor={anchor}
              dominantBaseline="middle"
              fontSize={10}
              fontFamily="DM Sans, sans-serif"
              fontWeight={600}
              fill="var(--muted)"
              letterSpacing="0.02em"
            >
              {lines.map((ln, li) => (
                <tspan
                  key={li}
                  x={lx}
                  dy={li === 0 ? (lines.length > 1 ? '-0.5em' : '0') : '1.2em'}
                >
                  {ln}
                </tspan>
              ))}
            </text>
          );
        })}

        {/* Centre dot */}
        <circle cx={CX} cy={CY} r={3} fill="var(--green-mid)" />
      </svg>

      <p className="radar-note">
        Each axis: fraction of a 95th-percentile product's impact per kg of
        meal. 100% = as impactful as the worst 5% of products in that category.
      </p>
    </div>
  );
}
