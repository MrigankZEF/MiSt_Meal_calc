/**
 * History — P6/P7.
 *
 * Meals tab:        sortable list (date / CO₂ / water) with open + delete.
 * Procurement tab:  aggregate dashboard with period filter + trend chart.
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
import ProcurementDashboard from '../components/ProcurementDashboard';
import { useAuth } from '../context/AuthContext';

// Period type is owned by ProcurementDashboard; re-declare locally for the state
type Period = '2w' | '1m' | '3m' | '1y' | 'all' | 'custom';

type HistoryTab = 'meals' | 'procurement';
type MealSort  =
  | 'newest' | 'oldest'
  | 'co2_desc'   | 'co2_asc'
  | 'water_desc' | 'water_asc'
  | 'land_desc'  | 'land_asc'
  | 'so2_desc'   | 'so2_asc'
  | 'p_desc'     | 'p_asc'
  | 'n_desc'     | 'n_asc';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-NL', { day: 'numeric', month: 'short', year: 'numeric' });
}

function buildLabel(d: RivmItemDetail): string {
  let base: string;
  if (d.stage === 'distribution') base = 'distribution';
  else if (d.stage === 'retail')   base = 'as bought';
  else                              base = d.prep_method || 'unspecified';
  const pkg = (d.packaging || '').trim();
  return pkg && pkg.toLowerCase() !== 'not packed' ? `${base} · ${pkg}` : base;
}

async function reconstructItems(
  ingredients: Array<{ rivm_item_id: number; primary_name: string; amount: number; unit: string; position: number }>,
): Promise<MealItem[]> {
  const sorted = [...ingredients].sort((a, b) => a.position - b.position);
  const details = await Promise.all(sorted.map(ing => getRivmItem(ing.rivm_item_id)));
  return sorted.map((ing, i) => {
    const d = details[i];
    const variant: IngredientVariant = {
      rivm_item_id: d.id, label: buildLabel(d), stage: d.stage,
      prep_method: d.prep_method, packaging: d.packaging, conditions: d.conditions,
      co2_kgco2eq: d.co2_kgco2eq, so2_kg: d.so2_kg, p_kg: d.p_kg,
      n_kg: d.n_kg, land_m2a: d.land_m2a, water_m3: d.water_m3,
    };
    return {
      uid: crypto.randomUUID(), rivm_item_id: ing.rivm_item_id,
      primary_name: ing.primary_name, variant, all_variants: [variant],
      amount: ing.amount, unit: ing.unit as Unit, nutrition: d.nutrition,
    };
  });
}

type SortField = 'date' | 'co2' | 'water' | 'land' | 'so2' | 'p' | 'n';

const MEAL_SORT_FIELD: Record<MealSort, { field: SortField; dir: 'asc' | 'desc' }> = {
  newest:     { field: 'date',  dir: 'desc' },
  oldest:     { field: 'date',  dir: 'asc'  },
  co2_desc:   { field: 'co2',   dir: 'desc' },
  co2_asc:    { field: 'co2',   dir: 'asc'  },
  water_desc: { field: 'water', dir: 'desc' },
  water_asc:  { field: 'water', dir: 'asc'  },
  land_desc:  { field: 'land',  dir: 'desc' },
  land_asc:   { field: 'land',  dir: 'asc'  },
  so2_desc:   { field: 'so2',   dir: 'desc' },
  so2_asc:    { field: 'so2',   dir: 'asc'  },
  p_desc:     { field: 'p',     dir: 'desc' },
  p_asc:      { field: 'p',     dir: 'asc'  },
  n_desc:     { field: 'n',     dir: 'desc' },
  n_asc:      { field: 'n',     dir: 'asc'  },
};

function getMealValue(m: MealListItem, field: SortField): number {
  switch (field) {
    case 'date':  return new Date(m.created_at).getTime();
    case 'co2':   return m.total_co2_kg   ?? -Infinity;
    case 'water': return m.total_water_m3 ?? -Infinity;
    case 'land':  return m.total_land_m2a ?? -Infinity;
    case 'so2':   return m.total_so2_kg   ?? -Infinity;
    case 'p':     return m.total_p_kg     ?? -Infinity;
    case 'n':     return m.total_n_kg     ?? -Infinity;
  }
}

function sortMeals(meals: MealListItem[], sort: MealSort): MealListItem[] {
  const { field, dir } = MEAL_SORT_FIELD[sort];
  return [...meals].sort((a, b) => {
    const va = getMealValue(a, field);
    const vb = getMealValue(b, field);
    return dir === 'desc' ? vb - va : va - vb;
  });
}

export default function History() {
  const { token } = useAuth();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<HistoryTab>('meals');
  const [mealSort, setMealSort]   = useState<MealSort>('newest');
  const [period, setPeriod]       = useState<Period>('3m');

  const [meals, setMeals]                 = useState<MealListItem[]>([]);
  const [mealsLoading, setMealsLoading]   = useState(false);
  const [mealsError, setMealsError]       = useState<string | null>(null);

  const [entries, setEntries]               = useState<ProcurementListItem[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);
  const [entriesError, setEntriesError]     = useState<string | null>(null);

  const [deletingMealId, setDeletingMealId]   = useState<string | null>(null);
  const [openingMealId, setOpeningMealId]     = useState<string | null>(null);
  const [deletingEntryId, setDeletingEntryId] = useState<string | null>(null);
  const [openingEntryId, setOpeningEntryId]   = useState<string | null>(null);
  const [actionError, setActionError]         = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setMealsLoading(true);
    listMeals(token)
      .then(setMeals)
      .catch(err => setMealsError(err instanceof Error ? err.message : 'Failed to load meals'))
      .finally(() => setMealsLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    setEntriesLoading(true);
    listProcurement(token)
      .then(setEntries)
      .catch(err => setEntriesError(err instanceof Error ? err.message : 'Failed to load orders'))
      .finally(() => setEntriesLoading(false));
  }, [token]);

  async function handleOpenMeal(meal: MealListItem) {
    if (!token || openingMealId) return;
    setOpeningMealId(meal.id); setActionError(null);
    try {
      const detail = await getMeal(token, meal.id);
      const items  = await reconstructItems(detail.ingredients);
      navigate('/meal', { state: { loadedItems: items, loadedMealName: detail.name } });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not open meal.');
    } finally { setOpeningMealId(null); }
  }

  async function handleDeleteMeal(meal: MealListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${meal.name}"? This cannot be undone.`)) return;
    setDeletingMealId(meal.id);
    try {
      await deleteMeal(token, meal.id);
      setMeals(prev => prev.filter(m => m.id !== meal.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Delete failed.');
    } finally { setDeletingMealId(null); }
  }

  async function handleOpenEntry(entry: ProcurementListItem) {
    if (!token || openingEntryId) return;
    setOpeningEntryId(entry.id); setActionError(null);
    try {
      const detail = await getProcurement(token, entry.id);
      const items  = await reconstructItems(detail.items);
      navigate('/procurement', { state: { loadedItems: items, loadedEntryName: detail.name } });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not open order.');
    } finally { setOpeningEntryId(null); }
  }

  async function handleDeleteEntry(entry: ProcurementListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${entry.name}"? This cannot be undone.`)) return;
    setDeletingEntryId(entry.id);
    try {
      await deleteProcurement(token, entry.id);
      setEntries(prev => prev.filter(e => e.id !== entry.id));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Delete failed.');
    } finally { setDeletingEntryId(null); }
  }

  const busy = !!(openingMealId || deletingMealId || openingEntryId || deletingEntryId);
  const sortedMeals = sortMeals(meals, mealSort);

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
          {meals.length > 0 && <span className="history-tab-count">{meals.length}</span>}
        </button>
        <button
          className={`history-tab${activeTab === 'procurement' ? ' active' : ''}`}
          onClick={() => { setActiveTab('procurement'); setActionError(null); }}
        >
          Procurement
          {entries.length > 0 && <span className="history-tab-count">{entries.length}</span>}
        </button>
      </div>

      {actionError && (
        <p className="save-meal-error" style={{ marginBottom: '12px' }}>{actionError}</p>
      )}

      {/* ── Meals tab ─────────────────────────────────────────────── */}
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
              <button className="btn-primary" style={{ marginTop: '16px' }} onClick={() => navigate('/meal')}>
                Go to Meal mode →
              </button>
            </div>
          ) : (
            <>
              {/* Sort control */}
              <div className="history-sort-bar">
                <label className="history-sort-label" htmlFor="meal-sort">Sort by</label>
                <select
                  id="meal-sort"
                  className="history-sort-select"
                  value={mealSort}
                  onChange={e => setMealSort(e.target.value as MealSort)}
                >
                  <optgroup label="Date">
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                  </optgroup>
                  <optgroup label="CO₂-eq (kg)">
                    <option value="co2_desc">Highest CO₂</option>
                    <option value="co2_asc">Lowest CO₂</option>
                  </optgroup>
                  <optgroup label="Water (m³)">
                    <option value="water_desc">Most water</option>
                    <option value="water_asc">Least water</option>
                  </optgroup>
                  <optgroup label="Land use (m²·a)">
                    <option value="land_desc">Most land</option>
                    <option value="land_asc">Least land</option>
                  </optgroup>
                  <optgroup label="Acidification (SO₂-eq)">
                    <option value="so2_desc">Highest SO₂</option>
                    <option value="so2_asc">Lowest SO₂</option>
                  </optgroup>
                  <optgroup label="FW Eutrophication (P-eq)">
                    <option value="p_desc">Highest P</option>
                    <option value="p_asc">Lowest P</option>
                  </optgroup>
                  <optgroup label="Mar. Eutrophication (N-eq)">
                    <option value="n_desc">Highest N</option>
                    <option value="n_asc">Lowest N</option>
                  </optgroup>
                </select>
              </div>

              <div className="history-list">
                {sortedMeals.map(meal => (
                  <div key={meal.id} className="history-card">
                    <div className="history-card-body">
                      <div className="history-card-name">{meal.name}</div>
                      {meal.notes && <div className="history-card-notes">{meal.notes}</div>}
                      <div className="history-card-meta">
                        <span>{formatDate(meal.created_at)}</span>
                        <span className="history-card-sep">·</span>
                        <span>{meal.ingredient_count} ingredient{meal.ingredient_count !== 1 ? 's' : ''}</span>
                        {meal.total_co2_kg != null && (
                          <>
                            <span className="history-card-sep">·</span>
                            <span className="history-card-co2">
                              {meal.total_co2_kg.toFixed(3)} kg CO₂
                            </span>
                          </>
                        )}
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
            </>
          )}
        </>
      )}

      {/* ── Procurement tab ──────────────────────────────────────── */}
      {activeTab === 'procurement' && (
        <>
          {entriesLoading ? (
            <p className="stub-desc">Loading your orders…</p>
          ) : entriesError ? (
            <p className="login-error">{entriesError}</p>
          ) : (
            <ProcurementDashboard
              entries={entries}
              period={period}
              onPeriodChange={setPeriod}
              busy={busy}
              onOpen={handleOpenEntry}
              onDelete={handleDeleteEntry}
              openingId={openingEntryId}
              deletingId={deletingEntryId}
              onGoToProcurement={() => navigate('/procurement')}
            />
          )}
        </>
      )}
    </div>
  );
}
