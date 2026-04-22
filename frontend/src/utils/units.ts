import type { Unit } from '../api/types';

/**
 * Converts a user-entered amount + unit to kilograms.
 * Liquids assume water density (1 g/ml ≈ 1 kg/L), which is reasonable
 * for most catering ingredients. `piece` uses a 100 g fallback.
 */
export function toKg(amount: number, unit: Unit): number {
  switch (unit) {
    case 'kg':    return amount;
    case 'g':     return amount / 1000;
    case 'L':     return amount;
    case 'ml':    return amount / 1000;
    case 'piece': return amount * 0.1; // 100 g per piece
  }
}

/**
 * Number of 100 g portions in the given amount.
 * RIVM LCA data is expressed per 100 g, so:
 *   impact = variant.metric * portions100g(amount, unit)
 */
export function portions100g(amount: number, unit: Unit): number {
  return toKg(amount, unit) * 10;
}
