import type { IngredientSearchResponse, RivmItemDetail } from './types';

// In dev the Vite proxy (vite.config.ts) forwards /api → http://localhost:8000
// so we use a relative base by default.  Set VITE_API_URL in production.
const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

/** Search ingredients by free-text query. Returns grouped results. */
export async function searchIngredients(
  mode: 'meal' | 'procurement',
  q: string,
  limit = 10,
): Promise<IngredientSearchResponse> {
  const url =
    `${BASE}/api/ingredients` +
    `?mode=${encodeURIComponent(mode)}` +
    `&q=${encodeURIComponent(q)}` +
    `&limit=${limit}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Search failed: ${res.status} ${res.statusText}`);
  return res.json() as Promise<IngredientSearchResponse>;
}

/** Fetch full detail for a single RIVM item, including nutrition join. */
export async function getRivmItem(id: number): Promise<RivmItemDetail> {
  const res = await fetch(`${BASE}/api/rivm_item/${id}`);
  if (!res.ok) throw new Error(`Item ${id} not found: ${res.status} ${res.statusText}`);
  return res.json() as Promise<RivmItemDetail>;
}
