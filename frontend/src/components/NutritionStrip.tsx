import type { ReactNode } from 'react';
import type { MealItem, NevoNutritionOut } from '../api/types';
import { portions100g } from '../utils/units';
// NEVO data is per 100 g — portions100g() is correct here.

// ── Inline SVG icons ──────────────────────────────────────────────────────

function IconFlame() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
      <path
        d="M6.5 1C6.5 1 4 3.5 4 6a2.5 2.5 0 005 0c0-1-.5-2-1.5-2.5.5 1 .2 2-.5 2.5C6 5 6 3.5 6.5 1z"
        fill="var(--amber)"
      />
      <path
        d="M6.5 12a3.5 3.5 0 003.5-3.5c0-1.2-.5-2.2-1.3-3C8.9 7 8.5 8 7.5 8.5 7.8 7.5 7.5 6.5 7 6c.2 1-.3 2-1 2.5A2 2 0 003 8.5 3.5 3.5 0 006.5 12z"
        fill="var(--amber)"
        opacity="0.75"
      />
    </svg>
  );
}

function IconProtein() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
      <circle cx="4" cy="4.5" r="2.5" stroke="var(--green-mid)" strokeWidth="1.3" />
      <circle cx="9" cy="8.5" r="2.5" stroke="var(--green-bright)" strokeWidth="1.3" />
      <line x1="5.8" y1="5.8" x2="7.2" y2="7.2" stroke="var(--green-mid)" strokeWidth="1.2" />
    </svg>
  );
}

function IconFat() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
      <path
        d="M6.5 2C6.5 2 3.5 5.5 3.5 8a3 3 0 006 0C9.5 5.5 6.5 2 6.5 2z"
        stroke="var(--green-mid)"
        strokeWidth="1.3"
        fill="rgba(82,183,136,0.15)"
      />
    </svg>
  );
}

function IconCarbs() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
      <rect x="2" y="5" width="9" height="5" rx="1.5"
        stroke="var(--green-mid)" strokeWidth="1.3" fill="rgba(82,183,136,0.1)" />
      <path d="M4 5V4a2.5 2.5 0 015 0v1" stroke="var(--green-mid)" strokeWidth="1.3" />
    </svg>
  );
}

function IconFibre() {
  return (
    <svg width="13" height="13" viewBox="0 0 13 13" fill="none" aria-hidden="true">
      <path d="M3 11C3 7 5 5 6.5 2" stroke="var(--green-bright)" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M6.5 2C8 5 10 7 10 11" stroke="var(--green-mid)" strokeWidth="1.3" strokeLinecap="round" />
      <path d="M4.5 7.5C5.5 6.5 7.5 6.5 8.5 7.5" stroke="var(--green-mid)" strokeWidth="1.1" strokeLinecap="round" />
    </svg>
  );
}

// ── Config ────────────────────────────────────────────────────────────────

interface NutrientDef {
  key: keyof NevoNutritionOut;
  label: string;
  unit: string;
  decimals: number;
  icon: ReactNode;
}

const NUTRIENTS: NutrientDef[] = [
  { key: 'kcal',      label: 'Energy',  unit: 'kcal', decimals: 0, icon: <IconFlame /> },
  { key: 'protein_g', label: 'Protein', unit: 'g',    decimals: 1, icon: <IconProtein /> },
  { key: 'fat_g',     label: 'Fat',     unit: 'g',    decimals: 1, icon: <IconFat /> },
  { key: 'carb_g',    label: 'Carbs',   unit: 'g',    decimals: 1, icon: <IconCarbs /> },
  { key: 'fibre_g',   label: 'Fibre',   unit: 'g',    decimals: 1, icon: <IconFibre /> },
];

// ── Component ─────────────────────────────────────────────────────────────

interface Props {
  items: MealItem[];
}

export default function NutritionStrip({ items }: Props) {
  const totals = NUTRIENTS.map(n => {
    const total = items.reduce((sum, item) => {
      if (item.nutrition == null) return sum;
      const val = item.nutrition[n.key];
      if (typeof val !== 'number') return sum;
      return sum + val * portions100g(item.amount, item.unit);
    }, 0);
    return { ...n, total };
  });

  return (
    <div className="nutrition-strip">
      {totals.map(n => (
        <div key={String(n.key)} className="nutrition-chip">
          <div className="nutrition-chip-icon">{n.icon}</div>
          <span className="nutrition-chip-value">{n.total.toFixed(n.decimals)}</span>
          <span className="nutrition-chip-label">
            {n.label}&thinsp;{n.unit}
          </span>
        </div>
      ))}
    </div>
  );
}
