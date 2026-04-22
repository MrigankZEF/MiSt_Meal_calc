/**
 * Simplified item card for Procurement mode.
 * No variant picker — procurement items are always distribution stage.
 */

import type { MealItem, Unit } from '../api/types';

interface Props {
  item: MealItem;
  onRemove: () => void;
  onAmountChange: (amount: number) => void;
  onUnitChange: (unit: Unit) => void;
}

const UNITS: Unit[] = ['g', 'kg', 'ml', 'L', 'piece'];

export default function ProcurementItemCard({
  item,
  onRemove,
  onAmountChange,
  onUnitChange,
}: Props) {
  const co2 = item.variant.co2_kgco2eq;

  return (
    <div className="ingredient-card">
      <div className="ingredient-header">
        <span className="ingredient-name">{item.primary_name}</span>
        <button
          className="ingredient-remove"
          onClick={onRemove}
          aria-label={`Remove ${item.primary_name}`}
        >
          ×
        </button>
      </div>

      <div className="ingredient-inputs">
        <input
          className="ingredient-qty"
          type="number"
          min={0}
          step={1}
          value={item.amount}
          onChange={e => onAmountChange(Math.max(0, Number(e.target.value)))}
          aria-label="Quantity"
        />
        <select
          className="ingredient-unit"
          value={item.unit}
          onChange={e => onUnitChange(e.target.value as Unit)}
          aria-label="Unit"
        >
          {UNITS.map(u => (
            <option key={u} value={u}>{u}</option>
          ))}
        </select>
      </div>

      {co2 != null && (
        <p className="ingredient-co2">
          {co2.toFixed(3)}&thinsp;kg CO₂-eq / kg
        </p>
      )}
    </div>
  );
}
