/**
 * ProcurementMode — shell layout for P4.
 *
 * Left panel: period label + search + item list + Analyse button.
 * Right panel: empty state.
 *
 * P7 will wire up the full procurement flow.
 */

function SearchIcon() {
  return (
    <svg
      className="search-icon"
      width="15"
      height="15"
      viewBox="0 0 15 15"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M10 10l3 3"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

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

/** Returns the ISO week number label for today, e.g. "Week 16, 2026" */
function currentWeekLabel(): string {
  const now = new Date();
  const start = new Date(now.getFullYear(), 0, 1);
  const week = Math.ceil(
    ((now.getTime() - start.getTime()) / 86400000 + start.getDay() + 1) / 7
  );
  return `Week ${week}, ${now.getFullYear()}`;
}

export default function ProcurementMode() {
  return (
    <div className="mode-layout">
      {/* ── Left panel ─────────────────────────────────────────────── */}
      <aside className="mode-left">
        {/* Period label */}
        <div className="period-bar">
          <span className="period-label">Period</span>
          <span className="period-value">{currentWeekLabel()}</span>
        </div>

        {/* Search */}
        <div className="panel-search">
          <div className="search-wrap">
            <SearchIcon />
            <input
              className="search-input"
              type="text"
              placeholder="Search product… (e.g. chicken fillet)"
              aria-label="Search procurement items"
            />
          </div>
        </div>

        {/* Item list (populated in P7) */}
        <div className="panel-items">
          <p className="panel-items-hint">
            Search for a product above to add it to your procurement list.
          </p>
        </div>

        {/* Analyse button */}
        <div className="panel-action">
          <button className="btn-primary" disabled>
            Analyse procurement
          </button>
        </div>
      </aside>

      {/* ── Right panel ────────────────────────────────────────────── */}
      <main className="mode-right">
        <div className="empty-state">
          <div className="empty-icon">
            <BasketIcon />
          </div>
          <h2 className="empty-title">Add items to get started</h2>
          <p className="empty-desc">
            Enter the products you purchased and their quantities, then click{' '}
            <em>Analyse procurement</em> to see the total environmental impact
            of your order.
          </p>
        </div>
      </main>
    </div>
  );
}
