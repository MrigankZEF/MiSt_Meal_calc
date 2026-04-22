import { Link, useLocation, useNavigate } from 'react-router-dom';

const SCREEN_TAGS: Record<string, string> = {
  '/meal': 'Meal mode',
  '/procurement': 'Procurement',
  '/history': 'History',
  '/login': 'Login',
};

function BackArrow() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M10 3L5 8L10 13"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Nav() {
  const location = useLocation();
  const navigate = useNavigate();
  const screenTag = SCREEN_TAGS[location.pathname];
  const showBack = location.pathname !== '/';

  return (
    <nav className="nav">
      <div className="nav-left">
        {showBack && (
          <button
            className="nav-back"
            onClick={() => navigate('/')}
            aria-label="Back to home"
          >
            <BackArrow />
            Back
          </button>
        )}
        <Link to="/" className="nav-logo">
          MiSt
        </Link>
        {screenTag && <span className="nav-screen-tag">{screenTag}</span>}
      </div>
      <span className="nav-badge">RIVM data</span>
    </nav>
  );
}
