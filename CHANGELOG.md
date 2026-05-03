# MiSt — Changelog

Newest-first. Each entry: date · author · summary, then bullet details.

---

- **2026-05-03 · Claude (CLI) · Railway deployment — single-service, frontend bundled into backend**
  - **`backend/Dockerfile` rewritten** as multi-stage build: Node 20 stage builds the React frontend (`npm ci && npm run build`); Python 3.12-slim stage installs the backend, copies scripts, bakes in `data/reference.db`, and copies the built `dist/` as `frontend_dist/`.
  - **`railway.json`** — `buildContext` changed from `"backend"` to `"."` (repo root) so the Dockerfile can reach both `backend/` and `data/`.
  - **`backend/app/main.py`** — production static file serving added: `/assets` StaticFiles mount for Vite-hashed JS/CSS; catch-all `/{full_path:path}` route serves the requested file if it exists in `frontend_dist/`, otherwise returns `index.html` (SPA fallback). Gracefully absent in local dev (guard: `if _FRONTEND_DIST.exists()`).
  - No CORS or `VITE_API_URL` config needed — same-origin serving.
  - Railway env vars required: `USER_DB_URL` (PostgreSQL plugin), `SECRET_KEY`.

---

- **2026-04-23 · Claude (CLI) · P8 complete — EAT-Lancet scoring + admin review**
  - **`eat_lancet_tag` table** added to reference DB (`EatLancetTag` ORM model): nevo_code PK, bucket, notes, confirmed_by, confirmed bool. Seeded by `scripts/seed_eat_lancet_tags.py`.
  - **Seed script**: maps 26 NEVO food-group names → EAT-Lancet buckets. 2328 rows inserted. RIVM coverage 331/344 = **96.2%** (above 90% threshold). High-confidence buckets auto-confirmed; "Bread", "Meat and poultry", "Fats and oils", etc. flagged `confirmed=False` for human review.
  - **`services/scoring/` package** (3 modules):
    - `buckets.py` — `get_item_buckets()` resolves (rivm_item_id → nevo_code → bucket), fallback = "other".
    - `level_mapping.py` — `BucketWeights` dataclass + `dimension_levels()` maps 8 dimensions to 0–4 levels using weight fractions. All thresholds from Willett et al. (2019).
    - `scorers.py` — `compute_scores()` / `compute_scores_async()`. Returns `{eat_lancet, planetary_health, dimension_levels}`. EAT weights: plant_volume 18 · whole_grains 16 · legumes 16 · animal_moderation 18 · low_processing 16 · veg_diversity 16. Planetary weights: plant_volume 24 · whole_grains 14 · legumes 18 · low_red_meat 24 · low_processing 12 · fruit_nuts 8.
  - **`POST /api/score`** — on-demand scoring endpoint (no auth). Called by frontend live results panel.
  - **`GET/PATCH /api/admin/eat-lancet`** — review/update bucket + confirmed status per NEVO code. Requires JWT.
  - **User DB models** (`Meal`, `ProcurementEntry`): added `eat_lancet_score` and `planetary_health_score` nullable Float columns. ⚠️ Deleted `data/user.db` in dev.
  - **Pydantic schemas** + **TypeScript types**: score fields added to `MealOut`, `MealListItem`, `ProcurementOut`, `ProcurementListItem`.
  - **`ScoreCard.tsx`**: two-panel component (EAT Alignment + Planetary Health). Shows numeric score, band label (Strong/Fair/Mixed/Weak) in band-appropriate colour, progress bar, expandable dimension breakdown (dot bars 0–4 per criterion).
  - **MealMode + ProcurementMode**: replaced "Coming in P8" placeholder with live ScoreCard. Scores fetched via `POST /api/score` on Calculate/Analyse click and on history-load. Scores also cached at save time.
  - **`/admin` route** (`AdminEatLancet.tsx`): table of all tags grouped by food group, filterable by "needs review". Inline bucket select + confirm checkbox; save per row via PATCH. Protected route.
  - **13 backend tests still pass.** TypeScript check: 0 errors.

---

- **2026-04-23 · Claude (CLI) · Bug fixes — zero totals, sort, custom date range**
  - **Root cause fixed**: `list_meals` and `list_procurement` were manually constructing list-item schemas without passing the totals fields — they silently defaulted to `null` (rendered as `0` in dashboard; sort-by-metric had no effect because all values were equal-null).
  - **Fix**: all 6 totals (`total_co2_kg`, `total_water_m3`, `total_land_m2a`, `total_so2_kg`, `total_p_kg`, `total_n_kg`) now explicitly passed in both list endpoint constructors.
  - **`compute_totals_async`**: replaced synchronous `compute_totals(ref_session, ...)` call (cross-thread sync session in async route) with `asyncio.to_thread` wrapper that creates its own fresh session inside the worker thread. No more `ref_session` FastAPI dependency on the two create endpoints.
  - **Meal sort expanded**: all 6 env metrics now available as sort options, grouped with `<optgroup>` (CO₂, Water, Land use, Acidification SO₂, FW Eutrophication P, Mar. Eutrophication N — each high/low direction). Sort uses `-Infinity` sentinel for null values so records without totals always sort to the bottom.
  - **Procurement dashboard — custom date range**: "Custom" period pill added alongside 2W/1M/3M/1Y/All; when selected shows From/To `<input type="date">` inputs. Filtering is client-side over the already-fetched entries list.
  - **Procurement dashboard — removed trend chart**: "CO₂-eq per order" proportional bars section removed per user feedback.
  - **VISION.md §10.1 updated**: cooking double-count note added clarifying that fix must follow RIVM methodology docs, not guesswork.

- **2026-04-23 · Claude (CLI) · Procurement dashboard + meal sort (initial)**
  - **Footprint service** (`app/services/footprint/compute.py`): `compute_totals(ref_session, items)` — converts amounts to kg (g/ml ÷1000, kg/L ×1, piece ×0.1), looks up `RivmItem` rows by ID, sums 6 env metrics. Mirrors frontend `toKg()`.
  - **Totals stored at save time**: `Meal` and `ProcurementEntry` models gain 6 nullable `Float` columns (`total_co2_kg`, `total_water_m3`, `total_land_m2a`, `total_so2_kg`, `total_p_kg`, `total_n_kg`). Computed on every `POST /api/meals` and `POST /api/procurement`.
  - **Procurement Dashboard** (`ProcurementDashboard.tsx`): period filter (2W/1M/3M/1Y/All/Custom), six aggregate metric cards (CO₂ highlighted), order list with per-order CO₂ badge.
  - **History > Meals**: sort dropdown (newest/oldest + CO₂/water high-low — expanded to all 6 metrics in the bug-fix commit above).
  - **History page refactored**: Meals and Procurement tabs; `ProcurementDashboard` extracted as a separate component.
  - ⚠️ **Dev DB note**: new columns require deleting `data/user.db` once so `create_all()` recreates tables with all columns. Previously saved meals/orders will have `null` totals and appear at the bottom of metric sorts until re-saved.

- **2026-04-23 · Claude (CLI) · P7 complete — Procurement mode**
  - **Backend models**: `ProcurementEntry` (id, user_id, name, notes, created_at, 6 totals) + `ProcurementItem` (id, entry_id, rivm_item_id, primary_name, amount, unit, position). Both in `UserBase` / user DB.
  - **`User`** gains `procurement_entries` relationship (cascade delete-orphan).
  - **Schemas** (`app/schemas/procurement.py`): `ProcurementIn`, `ProcurementItemIn`, `ProcurementOut`, `ProcurementItemOut`, `ProcurementListItem`.
  - **API** (`app/api/procurement.py`): `GET /api/procurement`, `POST /api/procurement`, `GET /api/procurement/{id}`, `DELETE /api/procurement/{id}`. All JWT-protected.
  - **`IngredientSearch`** gains optional `mode` prop (default `'meal'`); procurement mode uses `mode=procurement` → distribution-only results, different placeholder text.
  - **`ProcurementItemCard`**: simplified card (name + qty/unit + CO₂ hint, no variant picker — distribution items always have one variant). Default unit `kg`.
  - **`ProcurementMode.tsx`**: full implementation mirroring MealMode — search, item list, Analyse button, results panel (MetricChips + 3 chart views + nutrition strip + save section). Handles `location.state?.loadedItems` on mount to restore analysis from History "Open →".
  - **History tabs**: Meals / Procurement tab switcher with count badges. Open → reconstructs full `MealItem[]` and navigates to `/procurement` with router state.
  - **Exit criteria met**: add distribution products → analyse → save order → History > Procurement shows it → Open → restores analysis.

- **2026-04-22 · Claude (CLI) · P6 complete (History open/load) — load saved meals back into MealMode**
  - **`History.tsx` rewritten**: `handleOpen()` fetches `getMeal()`, parallel-fetches all `getRivmItem()` details, reconstructs full `MealItem[]` (including `IngredientVariant` with all 6 env metrics and `nutrition`), navigates to `/meal` with `{ state: { loadedItems, loadedMealName } }`.
  - **`MealMode.tsx`** updated: reads `location.state?.loadedItems` on mount via `useEffect([], [])`, sets items + `showResults(true)` + pre-fills meal name. Clears router state with `window.history.replaceState({}, '')` to prevent re-trigger on back-navigation.
  - **`buildLabel()` helper** in History mirrors backend `variant_label()` so reconstructed variant labels are consistent.
  - **`all_variants`** set to `[variant]` for loaded items (full list would require a re-search; acceptable limitation noted in code).
  - **CSS**: `.btn-history-open` added (green filled button, matches design system).

- **2026-04-22 · Claude (CLI) · P6 complete — auth + meal persistence**
  - **fastapi-users 15.x** wired up: JWT bearer transport, `BearerTransport` + `JWTStrategy` + `AuthenticationBackend`. Endpoints: `POST /auth/jwt/login`, `POST /auth/jwt/logout`, `POST /auth/register`, `GET /auth/users/me`, `PATCH /auth/users/me`.
  - **Postgres user DB** via SQLAlchemy async engine (`psycopg3` dialect). Separate `UserBase(DeclarativeBase)` to keep reference-DB (SQLite) and user-DB (Postgres) models strictly isolated.
  - **Models**: `User` (extends `SQLAlchemyBaseUserTableUUID`, table `auth_user`), `Meal`, `MealIngredient`. `auth_user` used instead of `user` to avoid PostgreSQL reserved word.
  - **Startup**: `_init_user_tables()` runs `metadata.create_all()` on boot with up-to-10 retries (handles Docker startup ordering). Alembic scaffold added for future production migrations.
  - **Meals API**: `GET /api/meals`, `POST /api/meals`, `GET /api/meals/{id}`, `DELETE /api/meals/{id}`. All endpoints require valid JWT.
  - **Frontend — AuthContext**: `useAuth()` hook; token persisted in `localStorage`; verifies stored token via `/auth/users/me` on app load; clears on 401.
  - **Login page**: email + password form with login/register toggle. On success navigates to `/meal`.
  - **History page**: lists saved meals (name, date, ingredient count); delete with confirm dialog; "not logged in" and "empty" states.
  - **MealMode save section**: Guest → "Sign in to save" + link. Logged-in → name input + save button. Success flash (3 s).
  - **Nav**: user name + Sign out (logged-in) or Sign in button (guest).
  - `docker-compose.yml` updated: Postgres `healthcheck` (`pg_isready`); backend `depends_on: db: condition: service_healthy`.
  - **Exit criteria met**: register → log in → add ingredients → calculate → save meal → log out → log in → History shows meal.

- **2026-04-20 · Claude (CLI) · P4 complete — React frontend shell with routing and design system**
  - Design source: `MiSt-standalone.html` (Claude Design export). Extracted exact tokens, layout dimensions, typography, spacing, and interaction patterns.
  - `frontend/src/theme/global.css` — full rewrite with all design-system classes: nav (fixed 56px, deep-green), landing (hero + two mode cards 340px), split mode layout (left 390px fixed, right flex-1), search input with icon, ingredient cards with variant pill + qty/unit inputs, metric chips, results tabs, nutrition strip, stub pages.
  - `frontend/src/components/Nav.tsx` — fixed nav: back arrow (on non-landing routes), MiSt serif logo, screen-tag pill, RIVM amber badge.
  - `frontend/src/routes/Landing.tsx` — hero section, two mode cards with SVG icons, hover animations, routing to `/meal` and `/procurement`.
  - `frontend/src/routes/MealMode.tsx` — split layout shell: search input, empty ingredient list, disabled Calculate button, empty-state right panel. Ready to fill in P5.
  - `frontend/src/routes/ProcurementMode.tsx` — same split layout with period label bar, stub. Ready for P7.
  - `frontend/src/App.tsx` — `BrowserRouter` + `Routes` for `/`, `/meal`, `/procurement`, `/history`, `/login`.
  - TypeScript clean. Vite boots in 203 ms.
  - **Exit criteria met** (P4: React scaffold, theme tokens, landing with two mode buttons, clicking into Meal mode renders empty search UI).

- **2026-04-20 · Claude (CLI) · Scoring fix + P2 complete — tiered ranking, NEVO nutrition ingest**
  - **Search scoring rebuilt**: tiered ladder — exact string → 120, all stems match → 100 − penalties, partial overlap → 65 + 8·|overlap|, fuzzy fallback. Scores primary_name + nevo_name_en + nevo_naam_nl, takes max — Dutch queries now resolve via NL name.
  - **`PROCESSED_WORDS` bug fixed**: stemming was applied to candidate before blocklist check — penalty never fired. Pre-stem the blocklist at module init.
  - **`primary_leads` tiebreaker**: demotes oddities like `Eggs chicken` for query `chicken` without touching score tiers.
  - **P2 — NEVO nutrition ingest**: `NevoNutrition` ORM model; `ingest_nevo.py` reads `NEVO2025_v9.0.xlsx`, maps 20 curated columns, dumps all 148 cols to `raw_nutrients` JSON. 2328 rows inserted, 331/344 RIVM NEVO codes joinable (96.2%). `get_rivm_item` attaches `nutrition` field.
  - **All 13 tests pass.**

- **2026-04-19 · Claude (CLI) · P3 complete — ingredient search API with grouped variants**
  - `backend/app/schemas/ingredient.py` — Pydantic v2 models: `IngredientVariant`, `IngredientGroup`, `IngredientSearchResponse`, `RivmItemDetail`.
  - `backend/app/services/matching/search.py` — `search_ingredients(session, mode, query, limit)`. Filters by stage (meal → retail+consumption, procurement → distribution), groups by NEVO code, scores with rapidfuzz, `variant_label()` emits readable labels.
  - `backend/app/api/ingredients.py` — `GET /api/ingredients` and `GET /api/rivm_item/{id}`.
  - 8 tests, all green.
  - **Exit criteria met** (P3: modular backend, grouped-variant search, OpenAPI auto-generated).

- **2026-04-19 · Claude (CLI) · P1 complete — RIVM ingestion (all 3 stages)**
  - `ingest_rivm.py` reads all three stage sheets, parses pipe-delimited names, stores `raw_name` + parsed fields.
  - Verification: `distribution=376, retail=376, consumption=411`. All 6 metrics preserved.
  - Must run via WSL Python (Windows UNC path → SQLite lock).
  - **Exit criteria met** (P1 counts match, all metrics stored).

- **2026-04-22 · Claude (CLI) · P5 complete — frontend connected to backend**
  - `src/api/types.ts` + `src/api/client.ts` — typed client with relative base URL (Vite proxy).
  - `src/hooks/useDebounce.ts` — 280 ms debounce.
  - `src/utils/units.ts` — `toKg()` + `portions100g()`.
  - `IngredientSearch.tsx` — live debounced search dropdown.
  - `MealItemCard.tsx` — variant picker, qty/unit inputs, amber cooking warning.
  - `MetricChips`, `BarsView`, `HeatmapView` — **unit bug fixed**: use `toKg()`, not `portions100g()`.
  - `RadarView` — **normalization fixed**: per-axis p95 references.
  - `NutritionStrip` — kcal/protein/fat/carbs/fibre totals.
  - `MealMode.tsx` — full implementation with Calculate, 3-tab chart view, PNG export (html2canvas).
  - `variant_label()` rewritten: `"supermarket"` → `"as bought"`, packaging appended with `·`.
  - **Proxy fix**: client.ts defaulted to relative base URL.
  - **Exit criteria met** (P5: feature-parity with v1 Meal mode on new stack).

- **2026-04-19 · Claude (CLI) · P0 complete — repo restructure**
  - v1 files moved to `legacy/`. Source xlsx to `data/source/` (gitignored).
  - `backend/` scaffold: pyproject.toml, Dockerfile, FastAPI `GET /health`, config, empty package tree.
  - `frontend/` scaffold: Vite + React 18 + TS, design tokens, landing stub.
  - Root: `docker-compose.yml`, `railway.json`, `.gitignore`, `README.md`.
  - **Exit criteria met.**

- **2026-04-19 · Claude (CLI) · Vision created**
  - Captured v1 inventory (§2), confirmed data sources (§3), laid out v2 schema (§4), grouped-variant UX (§5), EAT-Lancet scoring (§6), stack decisions (§7.1), design tokens (§8), phased delivery P0–P10 (§9).
