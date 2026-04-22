/**
 * ProcurementMode — P7.
 *
 * Left panel:  search (distribution-stage only) + simple item cards + Analyse button.
 * Right panel: empty state → results (metric chips, 3 chart views, nutrition strip)
 *              + Save procurement entry section.
 *
 * Shares all result components with MealMode — the MealItem[] type works
 * for procurement items (distribution variant, all_variants length = 1).
 */

import { type FormEvent, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { getRivmItem, saveProcurement } from '../api/client';
import type { IngredientGroup, MealItem, Unit } from '../api/types';
import BarsView from '../components/BarsView';
import HeatmapView from '../components/HeatmapView';
import IngredientSearch from '../components/IngredientSearch';
import MetricChips from '../components/MetricChips';
import NutritionStrip from '../components/NutritionStrip';
import ProcurementItemCard from '../components/ProcurementItemCard';
import RadarView from '../components/RadarView';
import { useAuth } from '../context/AuthContext';

type Tab = 'bars' | 'radar' | 'heatmap';

// ── icons ─────────────────────────────────────────────────────────────────

function BasketIcon() {
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
      <path d="M4 10h20l-2 12H6L4 10z" />
      <path d="M9 10L12 5" />
      <path d="M19 10L16 5" />
      <path d="M10 16h8" />
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

export default function ProcurementMode() {
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [items, setItems] = useState<MealItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('bars');
  const [exporting, setExporting] = useState(false);

  // ── Save state ────────────────────────────────────────────────────────
  const [entryName, setEntryName] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedOk, setSavedOk] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const resultsRef = useRef<HTMLDivElement>(null);

  // ── Load procurement entry from History "Open →" ──────────────────────
  useEffect(() => {
    const state = location.state as
      | { loadedItems?: MealItem[]; loadedEntryName?: string }
      | null;
    if (state?.loadedItems && state.loadedItems.length > 0) {
      setItems(state.loadedItems);
      setShowResults(true);
      if (state.loadedEntryName) setEntryName(state.loadedEntryName);
      window.history.replaceState({}, '');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Hide results when all items are removed
  useEffect(() => {
    if (items.length === 0) setShowResults(false);
  }, [items.length]);

  // ── Ingredient handlers ────────────────────────────────────────────────

  async function handleAddIngredient(group: IngredientGroup) {
    // Procurement mode: always distribution stage → first (only) variant
    const variant = group.variants[0];
    if (!variant) return;

    setAdding(true);
    try {
      const detail = await getRivmItem(variant.rivm_item_id);
      const newItem: MealItem = {
        uid: crypto.randomUUID(),
        rivm_item_id: variant.rivm_item_id,
        primary_name: group.primary_name,
        variant,
        all_variants: group.variants,
        amount: 1,
        unit: 'kg',
        nutrition: detail.nutrition,
      };
      setItems(prev => [...prev, newItem]);
    } catch (err) {
      console.error('Failed to load item detail:', err);
    } finally {
      setAdding(false);
    }
  }

  function handleRemove(uid: string) {
    setItems(prev => prev.filter(i => i.uid !== uid));
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
      link.download = `mist-procurement-${new Date().toISOString().slice(0, 10)}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      if (btn) btn.style.visibility = '';
      setExporting(false);
    }
  }

  // ── Save procurement entry ─────────────────────────────────────────────

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!token || items.length === 0 || saving) return;
    setSaving(true);
    setSaveError(null);
    try {
      await saveProcurement(token, {
        name: entryName.trim() || 'Untitled order',
        items: items.map((item, idx) => ({
          rivm_item_id: item.rivm_item_id,
          primary_name: item.primary_name,
          amount: item.amount,
          unit: item.unit,
          position: idx,
        })),
      });
      setSavedOk(true);
      setEntryName('');
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
        <IngredientSearch mode="procurement" onSelect={handleAddIngredient} />

        <div className="panel-items">
          {items.length === 0 ? (
            <p className="panel-items-hint">
              {adding
                ? 'Loading item…'
                : 'Search for a product above to add it to your procurement list.'}
            </p>
          ) : (
            items.map(item => (
              <ProcurementItemCard
                key={item.uid}
                item={item}
                onRemove={() => handleRemove(item.uid)}
                onAmountChange={a => handleAmountChange(item.uid, a)}
                onUnitChange={u => handleUnitChange(item.uid, u)}
              />
            ))
          )}
          {adding && items.length > 0 && (
            <p className="panel-items-hint" style={{ padding: '8px 0' }}>
              Adding item…
            </p>
          )}
        </div>

        <div className="panel-action">
          <button
            className="btn-primary"
            disabled={items.length === 0 || adding}
            onClick={() => setShowResults(true)}
          >
            {adding ? 'Loading…' : 'Analyse procurement'}
          </button>
        </div>
      </aside>

      {/* ── Right panel ────────────────────────────────────────────── */}
      <main className="mode-right">
        {!showResults || items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><BasketIcon /></div>
            <h2 className="empty-title">Add items to get started</h2>
            <p className="empty-desc">
              Enter the products you purchased and their quantities, then click{' '}
              <em>Analyse procurement</em> to see the total environmental impact
              of your order.
            </p>
          </div>
        ) : (
          <div className="results-panel" ref={resultsRef}>
            {/* Header row */}
            <div className="results-header">
              <h2 className="results-title">Procurement footprint</h2>
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
              Nutrition (total order, per 100 g data from NEVO 2025)
            </div>
            <NutritionStrip items={items} />

            {/* ── Save procurement ────────────────────────────────── */}
            <div className="save-meal-section">
              {!user ? (
                <div className="save-meal-guest">
                  <span className="save-meal-guest-text">
                    Sign in to save procurement orders to your history
                  </span>
                  <button
                    className="btn-outline save-meal-signin"
                    onClick={() => navigate('/login')}
                  >
                    Sign in →
                  </button>
                </div>
              ) : savedOk ? (
                <div className="save-meal-success">
                  <span>✓ Order saved!</span>
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
                      value={entryName}
                      onChange={e => setEntryName(e.target.value)}
                      placeholder="Name this order… (e.g. Sligro week 16)"
                      maxLength={300}
                      disabled={saving}
                    />
                    <button
                      className="btn-save-meal"
                      type="submit"
                      disabled={saving}
                    >
                      <SaveIcon />
                      {saving ? 'Saving…' : 'Save order'}
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
