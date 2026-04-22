import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const SCREEN_TAGS: Record<string, string> = {
  '/meal': 'Meal mode',
  '/procurement': 'Procurement',
  '/history': 'History',
  '/login': 'Sign in',
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
  const { user, logout } = useAuth();

  const screenTag = SCREEN_TAGS[location.pathname];
  const showBack = location.pathname !== '/';

  function handleLogout() {
    logout();
    navigate('/');
  }

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

      <div className="nav-right">
        <span className="nav-badge">RIVM data</span>

        {user ? (
          <>
            <span className="nav-user-name" title={user.email}>
              {user.full_name || user.email}
            </span>
            <button className="nav-logout" onClick={handleLogout}>
              Sign out
            </button>
          </>
        ) : (
          <button
            className="nav-login"
            onClick={() => navigate('/login')}
          >
            Sign in
          </button>
        )}
      </div>
    </nav>
  );
}
