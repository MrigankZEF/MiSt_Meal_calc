/**
 * MealMode — P5 full implementation.
 *
 * Left panel:  live ingredient search + variant/qty/unit cards.
 * Right panel: empty state → results (metric chips, 3 chart views,
 *              nutrition strip, EAT-Lancet placeholder) + PNG export.
 */

import { useEffect, useRef, useState } from 'react';
import { getRivmItem } from '../api/client';
import type { IngredientGroup, MealItem, Unit } from '../api/types';
import BarsView from '../components/BarsView';
import HeatmapView from '../components/HeatmapView';
import IngredientSearch from '../components/IngredientSearch';
import MealItemCard from '../components/MealItemCard';
import MetricChips from '../components/MetricChips';
import NutritionStrip from '../components/NutritionStrip';
import RadarView from '../components/RadarView';

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

// ── component ─────────────────────────────────────────────────────────────

export default function MealMode() {
  const [items, setItems] = useState<MealItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('bars');
  const [exporting, setExporting] = useState(false);

  const resultsRef = useRef<HTMLDivElement>(null);

  // Hide results when all ingredients are removed
  useEffect(() => {
    if (items.length === 0) setShowResults(false);
  }, [items.length]);

  // ── handlers ──────────────────────────────────────────────────────────

  async function handleAddIngredient(group: IngredientGroup) {
    // Prefer the retail-stage variant as default — it represents the
    // impact up to point of purchase and avoids cooking-energy double-counting.
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

  async function handleExport() {
    if (!resultsRef.current || exporting) return;
    setExporting(true);

    // Hide the export button so it doesn't appear in the captured image
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

  // ── render ────────────────────────────────────────────────────────────

  return (
    <div className="mode-layout">
      {/* ── Left panel ─────────────────────────────────────────────── */}
      <aside className="mode-left">
        {/* Debounced live search */}
        <IngredientSearch onSelect={handleAddIngredient} />

        {/* Ingredient card list */}
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

          {/* Spinner while a new item is loading */}
          {adding && items.length > 0 && (
            <p className="panel-items-hint" style={{ padding: '8px 0' }}>
              Adding ingredient…
            </p>
          )}
        </div>

        {/* Calculate button */}
        <div className="panel-action">
          <button
            className="btn-primary"
            disabled={items.length === 0 || adding}
            onClick={() => setShowResults(true)}
          >
            {adding ? 'Loading…' : 'Calculate meal footprint'}
          </button>
        </div>
      </aside>

      {/* ── Right panel ────────────────────────────────────────────── */}
      <main className="mode-right">
        {!showResults || items.length === 0 ? (
          /* Empty state */
          <div className="empty-state">
            <div className="empty-icon">
              <BarChartIcon />
            </div>
            <h2 className="empty-title">Your results will appear here</h2>
            <p className="empty-desc">
              Add ingredients on the left, then click{' '}
              <em>Calculate meal footprint</em> to see the breakdown across all
              six environmental impact categories.
            </p>
          </div>
        ) : (
          /* Results panel */
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

            {/* Chart area */}
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

            {/* EAT-Lancet placeholder */}
            <div className="score-placeholder">
              <div className="score-placeholder-icon" />
              <div>
                <div className="score-placeholder-label">EAT-Lancet score</div>
                <div className="score-placeholder-soon">Coming in P8</div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
