/**
 * History — P6: shows the list of saved meals for the logged-in user.
 *
 * Each card shows meal name, date, and ingredient count.
 * "Load" restores the meal into MealMode via navigation state (P7+: full reload).
 * "Delete" removes the meal after confirmation.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteMeal, listMeals } from '../api/client';
import type { MealListItem } from '../api/types';
import { useAuth } from '../context/AuthContext';

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('en-NL', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function History() {
  const { user, token } = useAuth();
  const navigate = useNavigate();

  const [meals, setMeals] = useState<MealListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    listMeals(token)
      .then(setMeals)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load meals'))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleDelete(meal: MealListItem) {
    if (!token) return;
    if (!window.confirm(`Delete "${meal.name}"? This cannot be undone.`)) return;
    setDeletingId(meal.id);
    try {
      await deleteMeal(token, meal.id);
      setMeals(prev => prev.filter(m => m.id !== meal.id));
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed');
    } finally {
      setDeletingId(null);
    }
  }

  // ── Not logged in ─────────────────────────────────────────────────────

  if (!user) {
    return (
      <div className="stub-page">
        <div className="stub-card">
          <h1 className="stub-title">Sign in to see your history</h1>
          <p className="stub-desc">
            Your saved meals will appear here once you have an account.
          </p>
          <button className="btn-primary" style={{ marginTop: '16px' }} onClick={() => navigate('/login')}>
            Sign in →
          </button>
        </div>
      </div>
    );
  }

  // ── Loading / error ───────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="stub-page">
        <p className="stub-desc">Loading your meals…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="stub-page">
        <div className="stub-card">
          <p className="login-error">{error}</p>
        </div>
      </div>
    );
  }

  // ── Empty state ───────────────────────────────────────────────────────

  if (meals.length === 0) {
    return (
      <div className="stub-page">
        <div className="stub-card">
          <h1 className="stub-title">No saved meals yet</h1>
          <p className="stub-desc">
            Build a meal in Meal mode and click{' '}
            <strong>Save meal</strong> to keep it here.
          </p>
          <button
            className="btn-primary"
            style={{ marginTop: '16px' }}
            onClick={() => navigate('/meal')}
          >
            Go to Meal mode →
          </button>
        </div>
      </div>
    );
  }

  // ── Meal list ─────────────────────────────────────────────────────────

  return (
    <div className="history-page">
      <div className="history-header">
        <h1 className="history-title">Saved meals</h1>
        <span className="history-count">{meals.length} meal{meals.length !== 1 ? 's' : ''}</span>
      </div>

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
                <span>{meal.ingredient_count} ingredient{meal.ingredient_count !== 1 ? 's' : ''}</span>
              </div>
            </div>
            <div className="history-card-actions">
              <button
                className="btn-ghost history-delete"
                onClick={() => handleDelete(meal)}
                disabled={deletingId === meal.id}
                aria-label={`Delete ${meal.name}`}
              >
                {deletingId === meal.id ? '…' : '✕'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
