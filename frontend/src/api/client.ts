import type {
  EatLancetTagItem,
  EatLancetTagUpdate,
  IngredientSearchResponse,
  MealIn,
  MealListItem,
  MealOut,
  ProcurementIn,
  ProcurementListItem,
  ProcurementOut,
  RivmItemDetail,
  ScoreResponse,
  UserOut,
} from './types';

// In dev the Vite proxy (vite.config.ts) forwards /api → http://localhost:8000
// so we use a relative base by default.  Set VITE_API_URL in production.
const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? '';

// ── Helpers ────────────────────────────────────────────────────────────────

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

async function assertOk(res: Response): Promise<void> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // ignore parse failure
    }
    throw new Error(detail);
  }
}

// ── Ingredient search ──────────────────────────────────────────────────────

/** Search ingredients by free-text query. Returns grouped results. */
export async function searchIngredients(
  mode: 'meal' | 'procurement',
  q: string,
  limit = 10,
): Promise<IngredientSearchResponse> {
  const url =
    `${BASE}/api/ingredients` +
    `?mode=${encodeURIComponent(mode)}` +
    `&q=${encodeURIComponent(q)}` +
    `&limit=${limit}`;
  const res = await fetch(url);
  await assertOk(res);
  return res.json() as Promise<IngredientSearchResponse>;
}

/** Fetch full detail for a single RIVM item, including nutrition join. */
export async function getRivmItem(id: number): Promise<RivmItemDetail> {
  const res = await fetch(`${BASE}/api/rivm_item/${id}`);
  await assertOk(res);
  return res.json() as Promise<RivmItemDetail>;
}

// ── Auth ───────────────────────────────────────────────────────────────────

/**
 * Log in with email + password.
 * fastapi-users login uses application/x-www-form-urlencoded with
 * `username` (= email) and `password` fields.
 */
export async function loginUser(
  email: string,
  password: string,
): Promise<{ access_token: string; token_type: string }> {
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${BASE}/auth/jwt/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  await assertOk(res);
  return res.json();
}

/** Register a new account. */
export async function registerUser(
  email: string,
  password: string,
  full_name: string,
): Promise<UserOut> {
  const res = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name }),
  });
  await assertOk(res);
  return res.json() as Promise<UserOut>;
}

/** Fetch the current user's profile. Throws if the token is invalid. */
export async function getCurrentUser(token: string): Promise<UserOut> {
  const res = await fetch(`${BASE}/auth/users/me`, {
    headers: authHeaders(token),
  });
  await assertOk(res);
  return res.json() as Promise<UserOut>;
}

// ── Meals ──────────────────────────────────────────────────────────────────

export async function saveMeal(token: string, meal: MealIn): Promise<MealOut> {
  const res = await fetch(`${BASE}/api/meals`, {
    method: 'POST',
    headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify(meal),
  });
  await assertOk(res);
  return res.json() as Promise<MealOut>;
}

export async function listMeals(token: string): Promise<MealListItem[]> {
  const res = await fetch(`${BASE}/api/meals`, {
    headers: authHeaders(token),
  });
  await assertOk(res);
  return res.json() as Promise<MealListItem[]>;
}

export async function getMeal(token: string, id: string): Promise<MealOut> {
  const res = await fetch(`${BASE}/api/meals/${id}`, {
    headers: authHeaders(token),
  });
  await assertOk(res);
  return res.json() as Promise<MealOut>;
}

export async function deleteMeal(token: string, id: string): Promise<void> {
  const res = await fetch(`${BASE}/api/meals/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  await assertOk(res);
}

// ── Procurement ────────────────────────────────────────────────────────────

export async function saveProcurement(
  token: string,
  entry: ProcurementIn,
): Promise<ProcurementOut> {
  const res = await fetch(`${BASE}/api/procurement`, {
    method: 'POST',
    headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  });
  await assertOk(res);
  return res.json() as Promise<ProcurementOut>;
}

export async function listProcurement(
  token: string,
): Promise<ProcurementListItem[]> {
  const res = await fetch(`${BASE}/api/procurement`, {
    headers: authHeaders(token),
  });
  await assertOk(res);
  return res.json() as Promise<ProcurementListItem[]>;
}

export async function getProcurement(
  token: string,
  id: string,
): Promise<ProcurementOut> {
  const res = await fetch(`${BASE}/api/procurement/${id}`, {
    headers: authHeaders(token),
  });
  await assertOk(res);
  return res.json() as Promise<ProcurementOut>;
}

export async function deleteProcurement(
  token: string,
  id: string,
): Promise<void> {
  const res = await fetch(`${BASE}/api/procurement/${id}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  await assertOk(res);
}

// ── Scoring ────────────────────────────────────────────────────────────────

/** Compute EAT-Lancet + Planetary Health scores for a list of items.
 *  No auth required — uses read-only reference DB. */
export async function scoreItems(
  items: Array<{ rivm_item_id: number; amount: number; unit: string }>,
): Promise<ScoreResponse> {
  const res = await fetch(`${BASE}/api/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  });
  await assertOk(res);
  return res.json() as Promise<ScoreResponse>;
}

// ── Admin — EAT-Lancet tag review ──────────────────────────────────────────

export async function listEatLancetTags(
  token: string,
  needsReview = false,
): Promise<EatLancetTagItem[]> {
  const url = `${BASE}/api/admin/eat-lancet${needsReview ? '?needs_review=true' : ''}`;
  const res = await fetch(url, { headers: authHeaders(token) });
  await assertOk(res);
  return res.json() as Promise<EatLancetTagItem[]>;
}

export async function updateEatLancetTag(
  token: string,
  nevo_code: number,
  update: EatLancetTagUpdate,
): Promise<EatLancetTagItem> {
  const res = await fetch(`${BASE}/api/admin/eat-lancet/${nevo_code}`, {
    method: 'PATCH',
    headers: { ...authHeaders(token), 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  await assertOk(res);
  return res.json() as Promise<EatLancetTagItem>;
}
