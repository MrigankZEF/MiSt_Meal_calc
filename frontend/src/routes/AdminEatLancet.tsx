/**
 * Admin — EAT-Lancet bucket review (P8).
 *
 * Logged-in users can review and confirm auto-classified NEVO buckets.
 * Grouped by food_group_en.  Filter: All / Needs Review.
 */

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listEatLancetTags, updateEatLancetTag } from '../api/client';
import type { EatLancetTagItem } from '../api/types';
import { useAuth } from '../context/AuthContext';

const BUCKETS = [
  'plant_veg', 'plant_fruit', 'whole_grain', 'refined_grain',
  'legume', 'nut_seed', 'dairy', 'red_meat', 'white_meat',
  'fish', 'egg', 'oil_healthy', 'oil_unhealthy',
  'ultra_processed', 'sugar_sweet', 'other',
];

function groupByFoodGroup(items: EatLancetTagItem[]): Map<string, EatLancetTagItem[]> {
  const map = new Map<string, EatLancetTagItem[]>();
  for (const item of items) {
    const key = item.food_group_en ?? '(no group)';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return map;
}

interface RowProps {
  item: EatLancetTagItem;
  onSaved: (updated: EatLancetTagItem) => void;
}

function TagRow({ item, onSaved }: RowProps) {
  const { token } = useAuth();
  const [bucket, setBucket] = useState(item.bucket);
  const [confirmed, setConfirmed] = useState(item.confirmed);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = bucket !== item.bucket || confirmed !== item.confirmed;

  async function handleSave() {
    if (!token || saving) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateEatLancetTag(token, item.nevo_code, {
        bucket,
        notes: item.notes,
        confirmed,
      });
      onSaved(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <tr className={`admin-row${!item.confirmed ? ' admin-row--review' : ''}`}>
      <td className="admin-cell admin-cell--code">{item.nevo_code}</td>
      <td className="admin-cell admin-cell--name">
        <span className="admin-dutch">{item.dutch_name ?? '–'}</span>
        {item.english_name && (
          <span className="admin-english">{item.english_name}</span>
        )}
      </td>
      <td className="admin-cell admin-cell--bucket">
        <select
          className="admin-select"
          value={bucket}
          onChange={e => setBucket(e.target.value)}
        >
          {BUCKETS.map(b => (
            <option key={b} value={b}>{b}</option>
          ))}
        </select>
      </td>
      <td className="admin-cell admin-cell--confirm">
        <label className="admin-confirm-label">
          <input
            type="checkbox"
            checked={confirmed}
            onChange={e => setConfirmed(e.target.checked)}
          />
          Confirmed
        </label>
      </td>
      <td className="admin-cell admin-cell--action">
        {dirty && (
          <button
            className="btn-admin-save"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? '…' : 'Save'}
          </button>
        )}
        {error && <span className="admin-error">{error}</span>}
        {item.notes && !item.confirmed && (
          <span className="admin-note">{item.notes}</span>
        )}
      </td>
    </tr>
  );
}

export default function AdminEatLancet() {
  const { user, token } = useAuth();
  const navigate = useNavigate();

  const [tags, setTags] = useState<EatLancetTagItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterReview, setFilterReview] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    listEatLancetTags(token, filterReview)
      .then(setTags)
      .catch(err => setError(err instanceof Error ? err.message : 'Load failed'))
      .finally(() => setLoading(false));
  }, [token, filterReview]);

  function handleSaved(updated: EatLancetTagItem) {
    setTags(prev => prev.map(t => t.nevo_code === updated.nevo_code ? updated : t));
  }

  if (!user) {
    return (
      <div className="stub-card" style={{ marginTop: 48 }}>
        <h2 className="stub-title">Sign in to access admin</h2>
        <button className="btn-primary" onClick={() => navigate('/login')}>
          Sign in →
        </button>
      </div>
    );
  }

  const needsReviewCount = tags.filter(t => !t.confirmed).length;
  const grouped = groupByFoodGroup(tags);

  return (
    <div className="admin-page">
      <div className="admin-header">
        <h1 className="admin-title">EAT-Lancet Bucket Review</h1>
        <p className="admin-subtitle">
          Review auto-classified food buckets. Unconfirmed entries affect scoring — confirm or
          correct the bucket per item.
        </p>
      </div>

      <div className="admin-toolbar">
        <label className="admin-filter-label">
          <input
            type="checkbox"
            checked={filterReview}
            onChange={e => setFilterReview(e.target.checked)}
          />
          Show only needs-review ({needsReviewCount})
        </label>
        <span className="admin-count">{tags.length} items shown</span>
      </div>

      {loading && <p className="stub-desc">Loading tags…</p>}
      {error && <p className="login-error">{error}</p>}

      {!loading && !error && (
        Array.from(grouped.entries()).map(([group, items]) => (
          <section key={group} className="admin-group">
            <h2 className="admin-group-title">
              {group}
              <span className="admin-group-count">
                {items.filter(t => !t.confirmed).length > 0 && (
                  <span className="admin-badge-review">
                    {items.filter(t => !t.confirmed).length} needs review
                  </span>
                )}
                {items.length} items
              </span>
            </h2>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>NEVO</th>
                  <th>Name</th>
                  <th>Bucket</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <TagRow key={item.nevo_code} item={item} onSaved={handleSaved} />
                ))}
              </tbody>
            </table>
          </section>
        ))
      )}
    </div>
  );
}
