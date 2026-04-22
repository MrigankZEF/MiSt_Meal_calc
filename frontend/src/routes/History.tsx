/**
 * History — P6: saved meals list with full load-back into Meal mode.
 *
 * "Open" reconstructs the full MealItem[] from the saved rivm_item_ids
 * (fetches variant + nutrition data in parallel) then navigates to /meal
 * with the result in router state — MealMode picks it up and shows results.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteMeal, getMeal, getRivmItem, listMeals } from '../api/client';
import type { IngredientVariant, MealItem, MealListItem, RivmItemDetail, Unit } from '../api/types';
import { useAuth } from '../context/AuthContext';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-NL', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Mirror of backend variant_label() — keeps labels consistent. */
function buildLabel(d: RivmItemDetail): string {
  let base: string;
  if (d.stage === 'distribution') base = 'distribution';
  else if (d.stage === 'retail')   base = 'as bought';
  else                              base = d.prep_method || 'unspecified';

  const pkg = (d.packaging || '').trim();
  return pkg && pkg.toLowerCase() !== 'not packed' ? `${base} · ${pkg}` : base;
}

export default function History() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [meals, setMeals]         = useState<MealListItem[]>([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [openingId, setOpeningId]   = useState<string | null>(null);
  const [openError, setOpenError]   = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    listMeals(token)
      .then(setMeals)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load meals'))
      .finally(() => setLoading(false));
  }, [token]);

  // ── Load a saved meal into Meal mode ──────────────────────────────────

  async function handleOpen(meal: MealListItem) {
    if (!token || openingId) return;
    setOpeningId(meal.id);
    setOpenError(null);
    try {
      // 1. Fetch meal with ingredient list (rivm_item_id, amount, unit, …)
      const detail = await getMeal(token, meal.id);
      const sorted = [...detail.ingredients].sort((a, b) => a.position - b.position);

      // 2. Fetch full variant + nutrition data for every ingredient in parallel
      const rivmDetails = await Promise.all(
        sorted.map(ing => getRivmItem(ing.rivm_item_id)),
      );

      // 3. Reconstruct MealItem objects — same shape MealMode uses locally
      const items: MealItem[] = sorted.map((ing, i) => {
        const d = rivmDetails[i];
        const variant: IngredientVariant = {
          rivm_item_id: d.id,
          label:        buildLabel(d),
          stage:        d.stage,
          prep_method:  d.prep_method,
          packaging:    d.packaging,
          conditions:   d.conditions,
          co2_kgco2eq:  d.co2_kgco2eq,
          so2_kg:       d.so2_kg,
          p_kg:         d.p_kg,
          n_kg:         d.n_kg,
          land_m2a:     d.land_m2a,
          water_m3:     d.water_m3,
        };
        return {
          uid:          crypto.randomUUID(),
          rivm_item_id: ing.rivm_item_id,
          primary_name: ing.primary_name,
          variant,
          all_variants: [variant],   // full variant list needs a search; acceptable for now
          amount:       ing.amount,
          unit:         ing.unit as Unit,
          nutrition:    d.nutrition,
        };
      });

      // 4. Navigate to /meal; MealMode reads this state and restores the analysis
      navigate('/meal', {
        state: { loadedItems: items, loadedMealName: detail.name },
      });
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : 'Could not open meal.');
    } finally {
      setOpeningId(null);
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────────

  async function handleDelete(meal: MealListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${meal.name}"? This cannot be undone.`)) return;
    setDeletingId(meal.id);
    try {
      await deleteMeal(token, meal.id);
      setMeals(prev => prev.filter(m => m.id !== meal.id));
    } catch (err) {
      setOpenError(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  }

  // ── Loading / error states ─────────────────────────────────────────────

  if (loading) {
    return (
      <div className="stub-page">
        <p className="stub-desc">Loading your meals…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stub-page">
        <div className="stub-card">
          <p className="login-error">{error}</p>
        </div>
      </div>
    );
  }

  if (meals.length === 0) {
    return (
      <div className="stub-page">
        <div className="stub-card">
          <h1 className="stub-title">No saved meals yet</h1>
          <p className="stub-desc">
            Build a meal in Meal mode and click <strong>Save meal</strong> to keep it here.
          </p>
          <button
            className="btn-primary"
            style={{ marginTop: '16px' }}
            onClick={() => navigate('/meal')}
          >
            Go to Meal mode →
          </button>
        </div>
      </div>
    );
  }

  // ── Meal list ─────────────────────────────────────────────────────────

  return (
    <div className="history-page">
      <div className="history-header">
        <h1 className="history-title">Saved meals</h1>
        <span className="history-count">
          {meals.length} meal{meals.length !== 1 ? 's' : ''}
        </span>
      </div>

      {openError && (
        <p className="save-meal-error" style={{ marginBottom: '12px' }}>{openError}</p>
      )}

      <div className="history-list">
        {meals.map(meal => (
          <div key={meal.id} className="history-card">
            <div className="history-card-body">
              <div className="history-card-name">{meal.name}</div>
              {meal.notes && (
                <div className="history-card-notes">{meal.notes}</div>
              )}
              <div className="history-card-meta">
                <span>{formatDate(meal.created_at)}</span>
                <span className="history-card-sep">·</span>
                <span>
                  {meal.ingredient_count} ingredient{meal.ingredient_count !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            <div className="history-card-actions">
              <button
                className="btn-history-open"
                onClick={() => handleOpen(meal)}
                disabled={!!openingId || !!deletingId}
                aria-label={`Open ${meal.name}`}
              >
                {openingId === meal.id ? 'Loading…' : 'Open →'}
              </button>

              <button
                className="btn-ghost history-delete"
                onClick={() => handleDelete(meal)}
                disabled={!!deletingId || !!openingId}
                aria-label={`Delete ${meal.name}`}
              >
                {deletingId === meal.id ? '…' : '✕'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
