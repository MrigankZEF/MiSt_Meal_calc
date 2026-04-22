import { useEffect, useRef, useState } from 'react';
import { searchIngredients } from '../api/client';
import type { IngredientGroup } from '../api/types';
import { useDebounce } from '../hooks/useDebounce';

interface Props {
  onSelect: (group: IngredientGroup) => void;
}

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
      <path d="M10 10l3 3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export default function IngredientSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<IngredientGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const debouncedQuery = useDebounce(query, 280);
  const wrapRef = useRef<HTMLDivElement>(null);

  // Fetch results when debounced query changes
  useEffect(() => {
    if (debouncedQuery.trim().length < 2) {
      setResults([]);
      setOpen(false);
      setLoading(false);
      setFetchError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setFetchError(null);

    searchIngredients('meal', debouncedQuery.trim())
      .then(r => {
        if (cancelled) return;
        setResults(r.results);
        setOpen(true); // always open, even if 0 results (shows "no results" msg)
        setFetchError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : String(err);
        console.error('[IngredientSearch] fetch failed:', msg);
        setResults([]);
        setFetchError(msg);
        setOpen(true); // open to show the error
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [debouncedQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    function handlePointerDown(e: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, []);

  function handleSelect(group: IngredientGroup) {
    onSelect(group);
    setQuery('');
    setOpen(false);
    setResults([]);
    setFetchError(null);
  }

  const showDropdown = open || (loading && debouncedQuery.trim().length >= 2);

  return (
    // position:relative + z-index here so the absolute dropdown stacks above
    // the .panel-items flex sibling even inside a flex column
    <div className="panel-search" style={{ position: 'relative', zIndex: 20 }}>
      <div className="search-wrap" ref={wrapRef}>
        <SearchIcon />
        <input
          className="search-input"
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Search ingredient… (e.g. chicken, aardappel)"
          aria-label="Search ingredients"
          aria-autocomplete="list"
          aria-expanded={open}
          autoComplete="off"
          spellCheck={false}
        />

        {showDropdown && (
          <div className="search-results" role="listbox" aria-label="Ingredient suggestions">
            {/* Loading state */}
            {loading ? (
              <div className="search-result-item search-result-loading">
                Searching…
              </div>
            ) : fetchError ? (
              /* Error state — shown in UI so user can see network problems */
              <div className="search-result-item search-result-error">
                ⚠ Could not reach API — is the backend running?
                <br />
                <span style={{ fontSize: 10, opacity: 0.7 }}>{fetchError}</span>
              </div>
            ) : results.length === 0 ? (
              /* No results */
              <div className="search-result-item search-result-loading">
                No results for &ldquo;{debouncedQuery}&rdquo;
              </div>
            ) : (
              /* Results list */
              results.map(group => (
                <div
                  key={`${group.primary_name}|${group.nevo_code ?? 'x'}`}
                  className="search-result-item"
                  role="option"
                  aria-selected={false}
                  onPointerDown={e => {
                    e.preventDefault();
                    handleSelect(group);
                  }}
                >
                  <span className="search-result-name">
                    {group.primary_name}
                    {/* Show NEVO English name as subtitle to distinguish
                        e.g. "Tomato av raw" vs "Tomato av boiled" */}
                    {group.nevo_name_en &&
                      group.nevo_name_en.toLowerCase() !==
                        group.primary_name.toLowerCase() && (
                        <span className="search-result-subtitle">
                          {group.nevo_name_en}
                        </span>
                    )}
                  </span>
                  <span className="search-result-group">
                    {group.variants.length === 1
                      ? '1 variant'
                      : `${group.variants.length} variants`}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
