import { useNavigate } from 'react-router-dom';

function PlateIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      stroke="var(--green-mid)"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="14" cy="15" r="7" />
      <path d="M11 15h6" />
      <path d="M14 12v6" />
      <path d="M20 7c0 1.5-1.5 3-3 3" />
      <path d="M20 7v4" />
    </svg>
  );
}

function BoxIcon() {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      stroke="var(--green-mid)"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 10l10-5 10 5v9l-10 5L4 19v-9z" />
      <path d="M14 5v14" />
      <path d="M4 10l10 5 10-5" />
      <path d="M9 7.5L19 12.5" />
    </svg>
  );
}

function ArrowRight() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M3 7h8M7 3l4 4-4 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="landing">
      <div className="landing-inner">
        <div className="landing-badge">Sustainability Analytics</div>

        <h1 className="landing-h1">
          What would you like
          <br />
          to analyse?
        </h1>

        <p className="landing-sub">
          Calculate the environmental footprint and nutrition profile of your
          food — for individual meals or bulk procurement orders.
        </p>

        <div className="mode-cards">
          {/* Meal mode */}
          <div className="mode-card" onClick={() => navigate('/meal')}>
            <div className="mode-icon">
              <PlateIcon />
            </div>
            <h2 className="mode-title">Meal Analysis</h2>
            <p className="mode-desc">
              Score individual dishes and recipes. Pick ingredients, choose prep
              methods, and see the full environmental and nutrition profile per
              meal.
            </p>
            <button
              className="mode-btn"
              onClick={(e) => {
                e.stopPropagation();
                navigate('/meal');
              }}
            >
              Start
              <ArrowRight />
            </button>
          </div>

          {/* Procurement mode */}
          <div className="mode-card" onClick={() => navigate('/procurement')}>
            <div className="mode-icon">
              <BoxIcon />
            </div>
            <h2 className="mode-title">Procurement Analysis</h2>
            <p className="mode-desc">
              Analyse your weekly or monthly supply orders. Enter what you
              bought and see aggregate sustainability metrics for the whole
              basket.
            </p>
            <button
              className="mode-btn"
              onClick={(e) => {
                e.stopPropagation();
                navigate('/procurement');
              }}
            >
              Start
              <ArrowRight />
            </button>
          </div>
        </div>

        <p className="landing-footer">
          No account needed &nbsp;·&nbsp; Desktop optimised &nbsp;·&nbsp; RIVM
          2024 environmental data
        </p>
      </div>
    </div>
  );
}
