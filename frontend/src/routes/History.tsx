/**
 * History — P6/P7: saved meals + procurement entries with full load-back.
 *
 * Two tabs: Meals and Procurement.
 * "Open" reconstructs the full MealItem[] from saved rivm_item_ids
 * (fetches variant + nutrition data in parallel) then navigates to the
 * relevant mode with the result in router state.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  deleteMeal,
  deleteProcurement,
  getMeal,
  getProcurement,
  getRivmItem,
  listMeals,
  listProcurement,
} from '../api/client';
import type {
  IngredientVariant,
  MealItem,
  MealListItem,
  ProcurementListItem,
  RivmItemDetail,
  Unit,
} from '../api/types';
import { useAuth } from '../context/AuthContext';

type HistoryTab = 'meals' | 'procurement';

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

/** Fetch all rivm details in parallel and reconstruct MealItem[]. */
async function reconstructItems(
  ingredients: Array<{
    rivm_item_id: number;
    primary_name: string;
    amount: number;
    unit: string;
    position: number;
  }>,
): Promise<MealItem[]> {
  const sorted = [...ingredients].sort((a, b) => a.position - b.position);
  const rivmDetails = await Promise.all(
    sorted.map(ing => getRivmItem(ing.rivm_item_id)),
  );
  return sorted.map((ing, i) => {
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
      all_variants: [variant],
      amount:       ing.amount,
      unit:         ing.unit as Unit,
      nutrition:    d.nutrition,
    };
  });
}

export default function History() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<HistoryTab>('meals');

  // ── Meals state ────────────────────────────────────────────────────────
  const [meals, setMeals]           = useState<MealListItem[]>([]);
  const [mealsLoading, setMealsLoading]   = useState(false);
  const [mealsError, setMealsError]       = useState<string | null>(null);
  const [deletingMealId, setDeletingMealId] = useState<string | null>(null);
  const [openingMealId, setOpeningMealId]   = useState<string | null>(null);

  // ── Procurement state ──────────────────────────────────────────────────
  const [entries, setEntries]           = useState<ProcurementListItem[]>([]);
  const [entriesLoading, setEntriesLoading]   = useState(false);
  const [entriesError, setEntriesError]       = useState<string | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);
  const [openingEntryId, setOpeningEntryId]   = useState<string | null>(null);

  // Shared action error (open/delete)
  const [actionError, setActionError] = useState<string | null>(null);

  // ── Load meals ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    setMealsLoading(true);
    listMeals(token)
      .then(setMeals)
      .catch(err => setMealsError(err instanceof Error ? err.message : 'Failed to load meals'))
      .finally(() => setMealsLoading(false));
  }, [token]);

  // ── Load procurement entries ──────────────────────────────────────────
  useEffect(() => {
    if (!token) return;
    setEntriesLoading(true);
    listProcurement(token)
      .then(setEntries)
      .catch(err => setEntriesError(err instanceof Error ? err.message : 'Failed to load orders'))
      .finally(() => setEntriesLoading(false));
  }, [token]);

  // ── Open a saved meal ─────────────────────────────────────────────────
  async function handleOpenMeal(meal: MealListItem) {
    if (!token || openingMealId) return;
    setOpeningMealId(meal.id);
    setActionError(null);
    try {
      const detail = await getMeal(token, meal.id);
      const items = await reconstructItems(detail.ingredients);
      navigate('/meal', {
        state: { loadedItems: items, loadedMealName: detail.name },
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not open meal.');
    } finally {
      setOpeningMealId(null);
    }
  }

  // ── Delete a saved meal ───────────────────────────────────────────────
  async function handleDeleteMeal(meal: MealListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${meal.name}"? This cannot be undone.`)) return;
    setDeletingMealId(meal.id);
    try {
      await deleteMeal(token, meal.id);
      setMeals(prev => prev.filter(m => m.id !== meal.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeletingMealId(null);
    }
  }

  // ── Open a saved procurement entry ────────────────────────────────────
  async function handleOpenEntry(entry: ProcurementListItem) {
    if (!token || openingEntryId) return;
    setOpeningEntryId(entry.id);
    setActionError(null);
    try {
      const detail = await getProcurement(token, entry.id);
      const items = await reconstructItems(detail.items);
      navigate('/procurement', {
        state: { loadedItems: items, loadedEntryName: detail.name },
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not open order.');
    } finally {
      setOpeningEntryId(null);
    }
  }

  // ── Delete a saved procurement entry ──────────────────────────────────
  async function handleDeleteEntry(entry: ProcurementListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${entry.name}"? This cannot be undone.`)) return;
    setDeletingEntryId(entry.id);
    try {
      await deleteProcurement(token, entry.id);
      setEntries(prev => prev.filter(e => e.id !== entry.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setDeletingEntryId(null);
    }
  }

  // ── Empty / loading states ─────────────────────────────────────────────

  const busy = !!(openingMealId || deletingMealId || openingEntryId || deletingEntryId);

  return (
    <div className="history-page">
      <div className="history-header">
        <h1 className="history-title">History</h1>
      </div>

      {/* Tab switcher */}
      <div className="history-tabs">
        <button
          className={`history-tab${activeTab === 'meals' ? ' active' : ''}`}
          onClick={() => { setActiveTab('meals'); setActionError(null); }}
        >
          Meals
          {meals.length > 0 && (
            <span className="history-tab-count">{meals.length}</span>
          )}
        </button>
        <button
          className={`history-tab${activeTab === 'procurement' ? ' active' : ''}`}
          onClick={() => { setActiveTab('procurement'); setActionError(null); }}
        >
          Procurement
          {entries.length > 0 && (
            <span className="history-tab-count">{entries.length}</span>
          )}
        </button>
      </div>

      {actionError && (
        <p className="save-meal-error" style={{ marginBottom: '12px' }}>{actionError}</p>
      )}

      {/* ── Meals tab ──────────────────────────────────────────────── */}
      {activeTab === 'meals' && (
        <>
          {mealsLoading ? (
            <p className="stub-desc">Loading your meals…</p>
          ) : mealsError ? (
            <p className="login-error">{mealsError}</p>
          ) : meals.length === 0 ? (
            <div className="stub-card" style={{ marginTop: 24 }}>
              <h2 className="stub-title">No saved meals yet</h2>
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
          ) : (
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
                      onClick={() => handleOpenMeal(meal)}
                      disabled={busy}
                      aria-label={`Open ${meal.name}`}
                    >
                      {openingMealId === meal.id ? 'Loading…' : 'Open →'}
                    </button>
                    <button
                      className="btn-ghost history-delete"
                      onClick={() => handleDeleteMeal(meal)}
                      disabled={busy}
                      aria-label={`Delete ${meal.name}`}
                    >
                      {deletingMealId === meal.id ? '…' : '✕'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Procurement tab ─────────────────────────────────────────── */}
      {activeTab === 'procurement' && (
        <>
          {entriesLoading ? (
            <p className="stub-desc">Loading your orders…</p>
          ) : entriesError ? (
            <p className="login-error">{entriesError}</p>
          ) : entries.length === 0 ? (
            <div className="stub-card" style={{ marginTop: 24 }}>
              <h2 className="stub-title">No saved orders yet</h2>
              <p className="stub-desc">
                Add products in Procurement mode and click{' '}
                <strong>Save order</strong> to keep it here.
              </p>
              <button
                className="btn-primary"
                style={{ marginTop: '16px' }}
                onClick={() => navigate('/procurement')}
              >
                Go to Procurement mode →
              </button>
            </div>
          ) : (
            <div className="history-list">
              {entries.map(entry => (
                <div key={entry.id} className="history-card">
                  <div className="history-card-body">
                    <div className="history-card-name">{entry.name}</div>
                    {entry.notes && (
                      <div className="history-card-notes">{entry.notes}</div>
                    )}
                    <div className="history-card-meta">
                      <span>{formatDate(entry.created_at)}</span>
                      <span className="history-card-sep">·</span>
                      <span>
                        {entry.item_count} item{entry.item_count !== 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>
                  <div className="history-card-actions">
                    <button
                      className="btn-history-open"
                      onClick={() => handleOpenEntry(entry)}
                      disabled={busy}
                      aria-label={`Open ${entry.name}`}
                    >
                      {openingEntryId === entry.id ? 'Loading…' : 'Open →'}
                    </button>
                    <button
                      className="btn-ghost history-delete"
                      onClick={() => handleDeleteEntry(entry)}
                      disabled={busy}
                      aria-label={`Delete ${entry.name}`}
                    >
                      {deletingEntryId === entry.id ? '…' : '✕'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
