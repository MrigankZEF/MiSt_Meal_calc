/**
 * MealMode — P5 + P6.
 *
 * Left panel:  live ingredient search + variant/qty/unit cards.
 * Right panel: empty state → results (metric chips, 3 chart views,
 *              nutrition strip, EAT-Lancet placeholder) + PNG export.
 *
 * P6 additions: "Save meal" section in results panel, backed by /api/meals.
 */

import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getRivmItem, saveMeal, scoreItems } from '../api/client';
import type { IngredientGroup, MealItem, ScoreResponse, Unit } from '../api/types';
import BarsView from '../components/BarsView';
import HeatmapView from '../components/HeatmapView';
import IngredientSearch from '../components/IngredientSearch';
import MealItemCard from '../components/MealItemCard';
import MetricChips from '../components/MetricChips';
import NutritionStrip from '../components/NutritionStrip';
import RadarView from '../components/RadarView';
import ScoreCard from '../components/ScoreCard';
import { useAuth } from '../context/AuthContext';

type Tab = 'bars' | 'radar' | 'heatmap';

// ── icons ─────────────────────────────────────────────────────────────────

function BarChartIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      stroke="var(--hint)"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="3"  y="14" width="5" height="10" rx="1" />
      <rect x="11" y="9"  width="5" height="15" rx="1" />
      <rect x="19" y="4"  width="5" height="20" rx="1" />
    </svg>
  );
}

function ExportIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7 1v8M4 6l3 3 3-3" />
      <path d="M2 11h10" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg
      width="13"
      height="13"
      viewBox="0 0 13 13"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 2h7l2 2v7a1 1 0 01-1 1H2a1 1 0 01-1-1V3a1 1 0 011-1z" />
      <path d="M4 12V7h5v5" />
      <path d="M4 2v3h4" />
    </svg>
  );
}

// ── component ─────────────────────────────────────────────────────────────

export default function MealMode() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [items, setItems] = useState<MealItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('bars');
  const [exporting, setExporting] = useState(false);

  // ── Score state ───────────────────────────────────────────────────────
  const [scores, setScores] = useState<ScoreResponse | null>(null);
  const [scoresLoading, setScoresLoading] = useState(false);

  // ── Save state ────────────────────────────────────────────────────────
  const [mealName, setMealName] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const resultsRef = useRef<HTMLDivElement>(null);

  // ── Load meal from History "Open →" ───────────────────────────────────
  useEffect(() => {
    const state = location.state as
      | { loadedItems?: MealItem[]; loadedMealName?: string }
      | null;
    if (state?.loadedItems && state.loadedItems.length > 0) {
      setItems(state.loadedItems);
      setShowResults(true);
      if (state.loadedMealName) setMealName(state.loadedMealName);
      // Clear the state so a back-navigation doesn't re-trigger this
      window.history.replaceState({}, '');
      // Re-score the loaded items
      runScoring(state.loadedItems);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Hide results when all ingredients are removed
  useEffect(() => {
    if (items.length === 0) { setShowResults(false); setScores(null); }
  }, [items.length]);

  // savedOk doesn't auto-dismiss — user navigates to History or keeps working

  // ── Scoring ────────────────────────────────────────────────────────────

  function runScoring(currentItems: MealItem[]) {
    if (currentItems.length === 0) return;
    setScoresLoading(true);
    setScores(null);
    scoreItems(currentItems.map(i => ({ rivm_item_id: i.rivm_item_id, amount: i.amount, unit: i.unit })))
      .then(setScores)
      .catch(err => console.error('Scoring failed:', err))
      .finally(() => setScoresLoading(false));
  }

  function handleCalculate() {
    setShowResults(true);
    runScoring(items);
  }

  // ── Ingredient handlers ────────────────────────────────────────────────

  async function handleAddIngredient(group: IngredientGroup) {
    const defaultVariant =
      group.variants.find(v => v.stage === 'retail') ?? group.variants[0];
    if (!defaultVariant) return;

    setAdding(true);
    try {
      const detail = await getRivmItem(defaultVariant.rivm_item_id);
      const newItem: MealItem = {
        uid: crypto.randomUUID(),
        rivm_item_id: defaultVariant.rivm_item_id,
        primary_name: group.primary_name,
        variant: defaultVariant,
        all_variants: group.variants,
        amount: 100,
        unit: 'g',
        nutrition: detail.nutrition,
      };
      setItems(prev => [...prev, newItem]);
    } catch (err) {
      console.error('Failed to load ingredient detail:', err);
    } finally {
      setAdding(false);
    }
  }

  function handleRemove(uid: string) {
    setItems(prev => prev.filter(i => i.uid !== uid));
  }

  function handleVariantChange(uid: string, rivm_item_id: number) {
    setItems(prev =>
      prev.map(item => {
        if (item.uid !== uid) return item;
        const variant = item.all_variants.find(v => v.rivm_item_id === rivm_item_id);
        if (!variant) return item;
        return { ...item, rivm_item_id, variant };
      }),
    );
  }

  function handleAmountChange(uid: string, amount: number) {
    setItems(prev =>
      prev.map(item => (item.uid === uid ? { ...item, amount } : item)),
    );
  }

  function handleUnitChange(uid: string, unit: Unit) {
    setItems(prev =>
      prev.map(item => (item.uid === uid ? { ...item, unit } : item)),
    );
  }

  // ── Export ────────────────────────────────────────────────────────────

  async function handleExport() {
    if (!resultsRef.current || exporting) return;
    setExporting(true);

    const btn = resultsRef.current.querySelector<HTMLElement>('.btn-export');
    if (btn) btn.style.visibility = 'hidden';

    try {
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(resultsRef.current, {
        backgroundColor: '#F5F2EA',
        scale: 2,
        useCORS: true,
        logging: false,
      });
      const link = document.createElement('a');
      link.download = `mist-meal-${new Date().toISOString().slice(0, 10)}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      if (btn) btn.style.visibility = '';
      setExporting(false);
    }
  }

  // ── Save meal ─────────────────────────────────────────────────────────

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!token || items.length === 0 || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await saveMeal(token, {
        name: mealName.trim() || 'Untitled meal',
        ingredients: items.map((item, idx) => ({
          rivm_item_id: item.rivm_item_id,
          primary_name: item.primary_name,
          amount: item.amount,
          unit: item.unit,
          position: idx,
        })),
      });
      setSavedOk(true);
      setMealName('');
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed — please try again.');
    } finally {
      setSaving(false);
    }
  }

  // ── render ────────────────────────────────────────────────────────────

  return (
    <div className="mode-layout">
      {/* ── Left panel ─────────────────────────────────────────────── */}
      <aside className="mode-left">
        <IngredientSearch onSelect={handleAddIngredient} />

        <div className="panel-items">
          {items.length === 0 ? (
            <p className="panel-items-hint">
              {adding
                ? 'Loading ingredient…'
                : 'Search for an ingredient above to add it to your meal.'}
            </p>
          ) : (
            items.map(item => (
              <MealItemCard
                key={item.uid}
                item={item}
                onRemove={() => handleRemove(item.uid)}
                onVariantChange={id => handleVariantChange(item.uid, id)}
                onAmountChange={a => handleAmountChange(item.uid, a)}
                onUnitChange={u => handleUnitChange(item.uid, u)}
              />
            ))
          )}
          {adding && items.length > 0 && (
            <p className="panel-items-hint" style={{ padding: '8px 0' }}>
              Adding ingredient…
            </p>
          )}
        </div>

        <div className="panel-action">
          <button
            className="btn-primary"
            disabled={items.length === 0 || adding}
            onClick={handleCalculate}
          >
            {adding ? 'Loading…' : 'Calculate meal footprint'}
          </button>
        </div>
      </aside>

      {/* ── Right panel ────────────────────────────────────────────── */}
      <main className="mode-right">
        {!showResults || items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><BarChartIcon /></div>
            <h2 className="empty-title">Your results will appear here</h2>
            <p className="empty-desc">
              Add ingredients on the left, then click{' '}
              <em>Calculate meal footprint</em> to see the breakdown across all
              six environmental impact categories.
            </p>
          </div>
        ) : (
          <div className="results-panel" ref={resultsRef}>
            {/* Header row */}
            <div className="results-header">
              <h2 className="results-title">Meal footprint</h2>
              <button
                className="btn-export"
                onClick={handleExport}
                disabled={exporting}
                aria-label="Export results as PNG"
              >
                <ExportIcon />
                {exporting ? 'Exporting…' : 'Export PNG'}
              </button>
            </div>

            {/* 6-metric summary chips */}
            <MetricChips items={items} />

            {/* Chart tab switcher */}
            <div className="results-tabs" role="tablist">
              {(['bars', 'radar', 'heatmap'] as Tab[]).map(tab => (
                <button
                  key={tab}
                  role="tab"
                  aria-selected={activeTab === tab}
                  className={`results-tab${activeTab === tab ? ' active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab === 'bars'    && 'Bar chart'}
                  {tab === 'radar'   && 'Radar'}
                  {tab === 'heatmap' && 'Heatmap'}
                </button>
              ))}
            </div>

            <div className="chart-area" role="tabpanel">
              {activeTab === 'bars'    && <BarsView    items={items} />}
              {activeTab === 'radar'   && <RadarView   items={items} />}
              {activeTab === 'heatmap' && <HeatmapView items={items} />}
            </div>

            {/* Nutrition strip */}
            <div className="results-section-label">
              Nutrition (total meal, per 100 g data from NEVO 2025)
            </div>
            <NutritionStrip items={items} />

            {/* EAT-Lancet scores */}
            {scoresLoading && (
              <p className="stub-desc" style={{ margin: '16px 0 8px' }}>
                Computing scores…
              </p>
            )}
            {!scoresLoading && scores && <ScoreCard scores={scores} />}

            {/* ── Save meal ──────────────────────────────────────────── */}
            <div className="save-meal-section">
              {!user ? (
                <div className="save-meal-guest">
                  <span className="save-meal-guest-text">Sign in to save meals to your history</span>
                  <button
                    className="btn-outline save-meal-signin"
                    onClick={() => navigate('/login')}
                  >
                    Sign in →
                  </button>
                </div>
              ) : savedOk ? (
                <div className="save-meal-success">
                  <span>✓ Meal saved!</span>
                  <button
                    type="button"
                    className="save-meal-history-link"
                    onClick={() => navigate('/history')}
                  >
                    View in History →
                  </button>
                  <button
                    type="button"
                    className="save-meal-again"
                    onClick={() => setSavedOk(false)}
                  >
                    Save another name
                  </button>
                </div>
              ) : (
                <>
                  <form className="save-meal-form" onSubmit={handleSave}>
                    <input
                      className="save-meal-input"
                      type="text"
                      value={mealName}
                      onChange={e => setMealName(e.target.value)}
                      placeholder="Name this meal… (optional)"
                      maxLength={300}
                      disabled={saving}
                    />
                    <button
                      className="btn-save-meal"
                      type="submit"
                      disabled={saving}
                    >
                      <SaveIcon />
                      {saving ? 'Saving…' : 'Save meal'}
                    </button>
                  </form>
                  {saveError && (
                    <p className="save-meal-error">{saveError}</p>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
