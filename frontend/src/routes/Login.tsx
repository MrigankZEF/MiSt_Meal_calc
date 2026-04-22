/**
 * Login / Register page — P6.
 *
 * A single page with a mode toggle: "Sign in" ↔ "Create account".
 * On success, navigates to /meal.
 */

import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

type Mode = 'login' | 'register';

export default function Login() {
  const { login, register } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password, fullName);
      }
      navigate('/meal');
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(
        msg.includes('LOGIN_BAD_CREDENTIALS') || msg.includes('400')
          ? 'Invalid email or password.'
          : msg.includes('REGISTER_USER_ALREADY_EXISTS')
          ? 'An account with that email already exists.'
          : msg || 'Something went wrong. Please try again.',
      );
    } finally {
      setLoading(false);
    }
  }

  function toggle() {
    setMode(m => (m === 'login' ? 'register' : 'login'));
    setError(null);
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">
          {mode === 'login' ? 'Sign in to MiSt' : 'Create your account'}
        </h1>

        <form onSubmit={handleSubmit} className="login-form" noValidate>
          {mode === 'register' && (
            <label className="login-field">
              <span className="login-label">Full name</span>
              <input
                className="login-input"
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                autoComplete="name"
                placeholder="Your name"
              />
            </label>
          )}

          <label className="login-field">
            <span className="login-label">Email</span>
            <input
              className="login-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              required
            />
          </label>

          <label className="login-field">
            <span className="login-label">Password</span>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              placeholder={mode === 'register' ? 'At least 8 characters' : ''}
              required
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button
            className="btn-primary login-submit"
            type="submit"
            disabled={loading || !email || !password}
          >
            {loading
              ? mode === 'login'
                ? 'Signing in…'
                : 'Creating account…'
              : mode === 'login'
              ? 'Sign in →'
              : 'Create account →'}
          </button>
        </form>

        <p className="login-toggle-hint">
          {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}
          {' '}
          <button type="button" className="login-toggle-link" onClick={toggle}>
            {mode === 'login' ? 'Create one' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  );
}
