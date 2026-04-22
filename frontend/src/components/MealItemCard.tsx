import type { MealItem, Unit } from '../api/types';

interface Props {
  item: MealItem;
  onRemove: () => void;
  onVariantChange: (rivm_item_id: number) => void;
  onAmountChange: (amount: number) => void;
  onUnitChange: (unit: Unit) => void;
}

const UNITS: Unit[] = ['g', 'kg', 'ml', 'L', 'piece'];

export default function MealItemCard({
  item,
  onRemove,
  onVariantChange,
  onAmountChange,
  onUnitChange,
}: Props) {
  const co2 = item.variant.co2_kgco2eq;

  return (
    <div className="ingredient-card">
      {/* Header: name + remove button */}
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

      {/* Variant badge — select if multiple variants, plain badge if single */}
      {item.all_variants.length > 1 ? (
        <select
          className="ingredient-variant"
          value={item.rivm_item_id}
          onChange={e => onVariantChange(Number(e.target.value))}
          aria-label="Select preparation variant"
        >
          {item.all_variants.map(v => (
            <option key={v.rivm_item_id} value={v.rivm_item_id}>
              {v.label}
            </option>
          ))}
        </select>
      ) : (
        <span className="ingredient-variant">{item.variant.label}</span>
      )}

      {/* Amount + unit inputs */}
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
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>

      {/* CO₂ hint — RIVM values are per kg of product */}
      {co2 != null && (
        <p className="ingredient-co2">
          {co2.toFixed(3)}&thinsp;kg CO₂-eq / kg
        </p>
      )}

      {/* Consumption-stage note — two flavours:
            • Actual cooking (boiling/frying/etc.) → double-count warning
            • Logistics-only (no preparation / chilling / freezing) → neutral note */}
      {item.variant.stage === 'consumption' && (() => {
        const COOKING = new Set([
          'boiling', 'pan frying', 'deep frying',
          'water cooker', 'microwave',
        ]);
        const method = item.variant.prep_method?.toLowerCase() ?? '';
        if (COOKING.has(method)) {
          return (
            <p className="ingredient-cooking-note">
              ⚠ Includes cooking energy — may double-count if multiple
              ingredients are cooked together.
            </p>
          );
        }
        // no preparation / chilled at consumer / freezing at consumer / dilution
        return (
          <p className="ingredient-logistics-note">
            Includes home transport &amp; handling beyond point of purchase
            (no cooking energy).
          </p>
        );
      })()}
    </div>
  );
}
