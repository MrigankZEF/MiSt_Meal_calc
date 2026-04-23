# MiSt — Vision & Build Plan (v2)

> **Living document.** Session rules are in `CLAUDE.md` (auto-loaded). Changelog lives in `CHANGELOG.md`. Read §0 first on context loss, then the relevant sections below.
>
> **Audience:** future-Claude (this CLI + VS Code), and Mrigank.

---

## 0. Current state

| | |
|---|---|
| **Phase** | P7 complete. Next: **P8** — EAT-Lancet bucket tagging + Level 1 scoring. |
| **Last session** | 2026-04-23 — bug fixes (zero totals, sort, custom date range), procurement dashboard, meal sort. |
| **Active features** | Auth (JWT, fastapi-users), Meal mode (save/load), Procurement mode (distribution-only, save/load), History (Meals + Procurement tabs, sort by 6 env metrics, period filter + custom range), Procurement Dashboard (6 aggregate metric cards). |
| **Parked** | Cooking double-count fix (§10.1 — needs RIVM docs review). Bar chart redesign (§10.2). Radar normalization (§10.3). |
| **Dev note** | Dev uses SQLite `data/user.db`; prod uses Postgres. Delete `data/user.db` if user-DB model columns change. |

---

## 1. Product vision

MiSt is a **one-shot sustainability tool for caterers and food-service operators** in the Netherlands. One hosted app, multi-tenant, two modes:

- **Procurement mode** — bulk buy analysis (weekly/monthly purchase lists from distributors like Sligro). Answers: *how sustainable is our supply chain this period?* Aggregate CO₂, water, land, acidification, eutrophication; nutrient profile of what was bought; EAT-Lancet alignment score of the basket.
- **Meal mode** — per-dish analysis. Same metrics per meal, with variant selection (raw / supermarket / boiled / pan-fried / …), save/rank meals, EAT-Lancet score per meal.

**Sold as:** a hosted SaaS product. Customers log in, save history, export reports.

**Target user story:** a caterer (e.g. APEL buys from Sligro) uploads their weekly order list and gets a shareable sustainability report in one click; or their chef scores individual recipes during menu planning.

---

## 2. V1 inventory (pre-v2 snapshot)

One-file FastAPI app (`app.py`, ~1180 lines): inline HTML/CSS/JS, DataFrame-backed fuzzy search, single SQLite `consumption` table (411 rows, 6 env metrics), no user persistence.
Preserved as `legacy/legacy_app.py`. Full detail in CHANGELOG.md entry "Vision created".

---

## 3. Source data (ground truth for the new schema)

### 3.1 RIVM environmental DB (`Database milieubelasting voedingsmiddelen ... (2).xlsx`)

Three stage sheets, identical column layout (header on row 3, `header=2`):

| Sheet | Rows | Unique NEVO | Name suffix pattern |
|---|---|---|---|
| `tot-en-met-distributie` | 376 | 330 | `… \| at distribution/NL Economic` |
| `tot-en-met-retail` | 376 | 330 | `… \| at supermarket/NL Economic` |
| `tot-en-met-consumptie` | 411 | 344 | `… \| <Prep>  \| consumed/NL Economic` |

Shared environmental columns (first 12):
`Naam, Eenheid, <blank>, kg CO2 eq, kg SO2 eq, kg P eq, kg N eq, m2a crop eq, m3, NEVO code, NEVO naam, NEVO productgroep, NEVO name, NEVO productgroup`

Metrics in full: CO₂ (kg CO₂ eq), **terrestrial acidification** (kg SO₂ eq), **freshwater eutrophication** (kg P eq), **marine eutrophication** (kg N eq), **land use** (m²a crop eq), **water** (m³).

Name grammar (pipe-delimited):
`<primary> | <packaging/ambient> | <weight> | [<Prep method>] | <stage suffix>`
— prep method only present on consumption rows (`Boiling`, `Pan frying`, `Oven`, `Microwave`, …).

### 3.2 NEVO nutrition DB (`NEVO2025_v9.0.xlsx`)

Sheet `NEVO2025`, **2328 rows × 148 cols**, values expressed **per 100 g**.

- Keys: `NEVO-code`, `Voedingsmiddelnaam/Dutch food name`, `Engelse naam/Food name`, `Voedingsmiddelgroep/Food group`, `Synoniem`.
- Macros: `ENERCJ (kJ)`, `ENERCC (kcal)`, `WATER (g)`, `PROT (g)`, `PROTPL (g)`, `PROTAN (g)`, `FAT (g)`, `FASAT (g)`, `FAMSCIS (g)`, `FAPU (g)`, `CHO (g)`, `SUGAR (g)`, `STARCH (g)`, `FIBT (g)`, `ALC (g)`.
- Full micronutrient panel (Na/K/Ca/Mg/Fe/Zn/Cu/Se/I, all vitamins, 80+ fatty-acid fractions). We store all columns, surface a curated subset.

**Other sheets** (`NEVO2025_Details`, `NEVO2025_Recepten_Recipes`, `NEVO2025_Referenties_References`, `NEVO2025_Nutrienten_Nutrients`) — parked, not in scope for v2 initial ingest.

### 3.3 Join key

`NEVO code` (int) — links every RIVM row to its nutrition profile. Not every RIVM row has a NEVO code; those stay in the DB with `nevo_code = NULL` and show no nutrition data.

---

## 4. V2 data model

Two separate databases, different lifecycles.

### 4.1 Reference DB — committed to git

**Local dev:** SQLite at `data/reference.db`.
**Prod (Railway):** baked into image or restored at startup from a checked-in `.sql` dump.

```
rivm_item
  id                    INT   PK
  stage                 TEXT  CHECK (stage IN ('distribution','retail','consumption'))
  nevo_code             INT   NULLABLE, indexed
  primary_name          TEXT  -- first segment of "Naam"
  prep_method           TEXT  NULLABLE -- 'raw','supermarket','boiling','pan frying', …
                              -- distribution → 'distribution' (single per NEVO)
                              -- retail → 'supermarket' (shown as 'raw' in UI for unprocessed items)
                              -- consumption → method word (Boiling, Pan frying, …)
  packaging             TEXT  NULLABLE
  conditions            TEXT  NULLABLE  -- e.g. "Ambient (average)", "Frozen"
  raw_name              TEXT  -- full original pipe-delimited string
  nevo_naam_nl          TEXT
  nevo_name_en          TEXT
  nevo_productgroup     TEXT
  co2_kgco2eq           REAL
  so2_kg                REAL  -- terrestrial acidification
  p_kg                  REAL  -- freshwater eutrophication
  n_kg                  REAL  -- marine eutrophication
  land_m2a              REAL
  water_m3              REAL

  INDEX (primary_name)
  INDEX (nevo_code)
  INDEX (stage)

nevo_nutrition
  nevo_code             INT   PK
  dutch_name            TEXT
  english_name          TEXT
  food_group_nl         TEXT
  food_group_en         TEXT
  synonym               TEXT
  kj                    REAL
  kcal                  REAL
  water_g               REAL
  protein_g             REAL
  protein_plant_g       REAL
  protein_animal_g      REAL
  fat_g                 REAL
  fat_saturated_g       REAL
  fat_mono_g            REAL
  fat_poly_g            REAL
  carb_g                REAL
  sugar_g               REAL
  starch_g              REAL
  fibre_g               REAL
  alcohol_g             REAL
  salt_mg               REAL  -- from NA
  -- full micronutrient columns preserved as-is in raw_nutrients JSON:
  raw_nutrients         JSON  -- all 148 original cols, lossless

  INDEX (english_name)
  INDEX (dutch_name)

eat_lancet_tag
  nevo_code             INT   PK
  bucket                TEXT  -- 'plant_veg','plant_fruit','whole_grain','refined_grain',
                              --  'legume','nut_seed','dairy','red_meat','white_meat',
                              --  'fish','egg','oil_healthy','oil_unhealthy',
                              --  'ultra_processed','sugar_sweet','other'
  notes                 TEXT
  confirmed_by          TEXT  -- who/what classified it (rule name or reviewer)
```

### 4.2 User DB — gitignored, Postgres on Railway

```
org
  id UUID PK, name TEXT, created_at TS, plan TEXT

app_user
  id UUID PK, org_id FK, email UNIQUE, hashed_password, role, created_at

session                       -- short-lived auth token
  id UUID PK, user_id FK, expires_at

meal
  id UUID PK, org_id FK, created_by FK,
  name TEXT, meal_date DATE, notes TEXT,
  servings INT DEFAULT 1,
  -- cached totals for list views (recompute on edit):
  total_co2_kg, total_water_m3, total_land_m2a,
  total_so2_kg, total_p_kg, total_n_kg,
  total_kcal, total_protein_g, total_fat_g, total_carb_g,
  eat_lancet_score REAL, planetary_health_score REAL,
  phdi_score REAL NULLABLE,
  created_at TS, updated_at TS

meal_item
  id UUID PK, meal_id FK, position INT,
  rivm_item_id INT,         -- FK to reference DB (soft ref; reference DB lives separately)
  amount REAL, unit TEXT    -- 'g','kg','ml','l','piece'

procurement_entry
  id UUID PK, org_id FK, created_by FK,
  name TEXT,                -- e.g. "Sligro order W14"
  period_start DATE, period_end DATE,
  supplier TEXT NULLABLE,
  notes TEXT,
  -- cached totals (same fields as meal):
  total_co2_kg, total_water_m3, total_land_m2a,
  total_so2_kg, total_p_kg, total_n_kg,
  total_kcal, total_protein_g, …,
  eat_lancet_score REAL,
  created_at, updated_at

procurement_item
  id UUID PK, entry_id FK, position INT,
  rivm_item_id INT,         -- always stage='distribution' in procurement mode
  amount REAL, unit TEXT    -- typically kg
```

**Decision:** procurement UI MVP only collects **item name + quantity** (per user). Supplier / period / cost deferred but columns kept so we don't migrate twice.

---

## 5. Matching & UX — grouped variants

Current behaviour (v1): search "sweet potato" → shows three rows with the full `| ambient | LDPE | 500g | Boiling | consumed/NL Economic` tail. Unreadable.

**New behaviour:**

### Meal mode
- Search returns **groups keyed by `primary_name`**. Each group includes one card per available variant drawn from *retail* + *consumption*:
  - retail row → labelled `raw (supermarket)` for unprocessed items, or the processed form's name as-is (e.g. "Chips, frozen pre-fried" at supermarket).
  - consumption rows → labelled by their `prep_method` (`boiled`, `pan-fried`, `oven`, `microwave`, …).
- Card shows only `primary_name` + variant suffix. Packaging/weight/stage suffix hidden.
- Example for `sweet potato`:
  ```
  Sweet potatoes
    ○ raw (supermarket)
    ○ boiled
    ○ pan-fried
  ```

### Procurement mode
- Search only hits **distribution** stage. One row per NEVO code. Cards show `primary_name` only, no variant chooser.

---

## 6. Scoring — EAT-Lancet (per `eat_lancet_scoring_guide.md`)

Implemented exactly per the guide. No hallucinated weights.

### 6.1 Level 1 — fast, intuitive

Both scores computed on every meal/procurement save:

**EAT-Lancet Alignment Score** (weights sum 100):
Plant volume 18 · Whole grains 16 · Legumes 16 · Animal protein moderation 18 · Low processing 16 · Vegetable diversity 16

**Planetary Health Meal Score** (weights sum 100):
Plant volume 24 · Whole grains 14 · Legumes 18 · Low red meat 24 · Low processing 12 · Fruit/nuts 8

Each dimension is scored `0–4`, contribution = `(level/4) × weight`. Sum, clamp `[0, 100]`.

Interpretation bands (shared): **80–100 Strong · 60–79 Fair · 40–59 Mixed · <40 Weak**.

### 6.2 Level 2 — PHDI (toggle, off by default)

Dimensions: Whole grains 14, Vegetables 14, Plant volume 14, Legumes 14, Fruit/nuts 12, Animal moderation 12, Dairy moderation 10, Low processing 10. Same `level/4 × weight` formula, clamp `[0, 100]`.

### 6.3 The 0–4 mapping is the real work

**To be built from scratch** (decision 2026-04-19). Lives as a rules module, not a hidden heuristic:

```
services/scoring/
  buckets.py          # EAT-Lancet bucket classifier (nevo_code → bucket)
                      # sourced from eat_lancet_tag table
  level_mapping.py    # bucket composition → 0-4 level per dimension
                      # each rule is commented with its threshold + source
  scorers.py          # EAT, Planetary, PHDI formulas from the guide
```

Workflow to populate `eat_lancet_tag`:
1. Seed rules based on NEVO food-group names (`Voedingsmiddelgroep`): e.g. "Legumes" group → `legume`, "Red meat" → `red_meat`, etc.
2. Auto-assign where confident; flag ambiguous for human review in an admin UI.
3. Mrigank reviews + confirms in batches.

**No scoring goes live until `eat_lancet_tag` coverage > 90% of NEVO codes.**

---

## 7. Architecture

### 7.1 Stack decisions (2026-04-19)

| Concern | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.12) | Keep pandas-era code; async-ready; great OpenAPI |
| Reference data | **SQLite** committed to git | Tiny, versionable, fits Railway deploy |
| User data | **Postgres** on Railway | Multi-tenant, real app |
| ORM / migrations | **SQLAlchemy + Alembic** | Standard; user DB needs migrations |
| Frontend | **React + Vite + TypeScript** | Long-term project; typed API client; complex UX (grids, charts, auth) |
| Styling | **Plain CSS + design tokens** preserving v1 theme | See §8 |
| Charts | **recharts** or **visx** | Decide at P5 |
| Auth | `fastapi-users` (JWT) | Land in P6, not before |
| Deploy | **Railway** (Docker) | User preference; Postgres addon; Docker = reproducible |
| CI | GitHub Actions — lint, typecheck, tests | Add at P3 |

### 7.2 Repo layout

```
mist-mealcalc/
  VISION.md                     ← this file
  README.md                     ← quickstart (updated per phase)
  backend/
    pyproject.toml              ← replaces requirements.txt
    Dockerfile
    alembic.ini
    alembic/versions/
    app/
      main.py                   ← FastAPI bootstrap
      config.py                 ← settings (env vars)
      deps.py                   ← DI (db sessions, current user)
      api/
        __init__.py
        ingredients.py          ← search/lookup endpoints
        meals.py                ← CRUD meals
        procurement.py          ← CRUD procurement entries
        scoring.py              ← score calculation endpoint
        auth.py                 ← (P6+)
        admin.py                ← classification review (P8)
      services/
        matching/               ← fuzzy matching + grouped-variant logic
        units/                  ← unit conversion
        footprint/              ← aggregate metrics
        nutrition/              ← aggregate kcal / protein / …
        scoring/                ← EAT-Lancet + PHDI (§6.3)
      models/
        reference.py            ← read-only ORM for reference DB
        user.py                 ← user DB models
      schemas/                  ← Pydantic request/response types
      db/
        reference_session.py
        user_session.py
    scripts/
      ingest_rivm.py            ← builds reference.db from RIVM xlsx (all 3 stages)
      ingest_nevo.py            ← adds nevo_nutrition table
      seed_eat_lancet_tags.py   ← initial bucket seeding
    tests/
      unit/
      integration/
  frontend/
    package.json
    vite.config.ts
    tsconfig.json
    src/
      main.tsx
      App.tsx
      routes/
        Landing.tsx             ← mode selector
        MealMode.tsx
        ProcurementMode.tsx
        History.tsx
        Login.tsx               ← (P6+)
      components/
        IngredientSearch.tsx
        VariantPicker.tsx
        MealList.tsx
        ImpactBars.tsx / Radar / Heatmap (preserved from v1)
        ReportExport.tsx        ← PNG export, ported from v1 canvas code
        ScoreCard.tsx           ← EAT + Planetary bands
      api/                      ← typed client generated from OpenAPI
      theme/
        tokens.css              ← §8 design tokens
        fonts.css               ← DM Serif + DM Sans
  data/
    reference.db                ← committed
    source/                     ← original xlsx files (already present)
    user.db                     ← gitignored (dev only)
  legacy/
    legacy_app.py               ← v1 `app.py` preserved
    legacy_ingest.py            ← v1 ingest script
  docker-compose.yml            ← dev: fastapi + postgres + vite
  railway.json                  ← prod deploy config
```

### 7.3 API surface (initial)

```
GET    /api/ingredients?mode={meal|procurement}&q=<term>
         → grouped results: [{primary_name, nevo_code, variants: [{id, label, stage, prep_method, co2, …}]}]
GET    /api/rivm_item/{id}
         → single item with nutrition joined

POST   /api/meals          (auth P6+)    body: {name, date, items:[{rivm_item_id, amount, unit}]}
GET    /api/meals
GET    /api/meals/{id}
PUT    /api/meals/{id}
DELETE /api/meals/{id}

POST   /api/procurement                    similar shape
GET    /api/procurement
…

POST   /api/score    body: {items:[...]}
         → {eat_lancet, planetary_health, phdi?, dimension_levels:{...}}

POST   /api/export/csv      body: {meal|procurement id}
POST   /api/export/png      (optional server-side; client-side preferred)
```

---

## 8. Design system — preserve v1 theme

**Design goal:** v2 UI must feel like a natural successor to v1. Same serif-heading / sans-body rhythm, same deep-green / cream / amber palette. No restart.

### Tokens (lifted verbatim from v1 `:root`)

```css
:root {
  --bg:         #F5F2EA;
  --bg-alt:     #EAE6DA;
  --surface:    #FFFFFF;

  --green-deep:   #1A3A2A;
  --green-mid:    #2D6A4F;
  --green-bright: #52B788;
  --green-light:  #B7E4C7;
  --green-pale:   #D8F3DC;

  --amber:       #D4A017;
  --amber-light: #F4E4B0;

  --text:  #1A1A18;
  --muted: #5A5A50;
  --hint:  #9A9A8A;

  --red: #E8523A;

  --border:        rgba(26,58,42,0.15);
  --border-strong: rgba(26,58,42,0.30);

  --r:    6px;
  --r-lg: 12px;
}
```

**Typography:** `DM Serif Display` for panel titles / numeric totals, `DM Sans` (300/400/500/600) for everything else.

**Components to port 1:1 from v1:**
- Nav bar (deep-green, white logo, amber "RIVM data" pill)
- Panel card (white surface, 12px radius, 0.5px border)
- Match card (cream bg, hover = pale green, selected = green-pale)
- Totals chips (deep-green bg, green-light serif numbers)
- Three result views: Bars / Radar / Heatmap
- PNG report exporter (port the canvas code to a React component or `html2canvas` — decide at P5)

---

## 9. Phasing

Each phase leaves the app working and demoable. Stop at each boundary for Mrigank to try it.

| Phase | Scope | Exit criteria |
|---|---|---|
| **P0** | Repo restructure scaffold; move v1 into `legacy/`; write this VISION.md; pyproject, Dockerfile, Vite scaffold; Railway-ready docker-compose | `docker compose up` boots empty backend + empty frontend |
| **P1** | `ingest_rivm.py` → all 3 stages into `rivm_item`. All 6 metrics preserved. Raw name + parsed fields both stored. | `SELECT COUNT(*) FROM rivm_item GROUP BY stage` returns expected counts (376/376/411). `legacy_app.py` still boots against the old DB (parallel) |
| **P2** | `ingest_nevo.py` → `nevo_nutrition`. Lossless `raw_nutrients` JSON column holds all 148 cols. | Nutrition lookup works for any NEVO code present in both tables |
| **P3** | Modular FastAPI backend. `/api/ingredients` with grouped variants. OpenAPI schema auto-generated. Old UI temporarily switched to hit new API (proves parity). | All v1 flows work through new backend |
| **P4** | React + Vite frontend scaffold. Theme tokens in place. Landing screen with two mode buttons. | Click into Meal mode renders an empty search UI |
| **P5** | Meal mode complete: grouped-variant search, meal list with qty/unit, totals, 3 result views, PNG export ported. | Feature-parity with v1 Meal mode, but using new API and new UI |
| **P6** | Auth: orgs, users, login. Meals persisted per user. History page. | Can log in, save a meal, log out, log back in, see it |
| **P7** | Procurement mode. Minimal UI (name + quantity per line). Save/load procurement entries. | Can create a procurement entry, see totals, return to it |
| **P8** | EAT-Lancet classification: bucket tagging + admin review UI. Level 1 scoring (EAT + Planetary) on meals and procurement. | ≥90% NEVO-code coverage; scores appear on meal/procurement detail |
| **P9** | PHDI Level 2 toggle. | PHDI score computed and displayed when enabled |
| **P10** | File-upload ingestion for procurement lists (xlsx/csv). Dutch-name fallback. Preview → confirm → commit. | Upload a Sligro-style order list, see it parsed into line items |

---

## 10. Open questions / decisions pending

- [ ] **Procurement upload file format** — do we have a real example of APEL's order list? Needed before P10.
- [ ] **Piece weights** — v1 has 10 manual entries; we'll need a broader mapping. Sources? Derive from NEVO `Hoeveelheid` where possible?
- [ ] **Density for ml/L** — keep `=1` heuristic or build a per-food density table?
- [ ] **Multi-language UI** — NL/EN toggle for caterer-facing UI? Most caterers here read Dutch. Backend already carries both names.
- [ ] **Raw↔cooked yield factors** — if someone enters "200 g raw potatoes, boiled", should we convert? Out of scope for v2; parked.
- [ ] **"Alternative" swap feature** — v1 suggests a lower-impact item from the same `productgroup`. Port as-is or redesign?
- [ ] **PNG report design update** — reuse v1 canvas code verbatim, or redesign with the two new modes?
- [ ] **Per-org branding** — down the line, do customers want their logo on exported reports?
- [ ] **Consumption-stage UX — cooking double-count problem** *(parked — resolve after reviewing RIVM methodology docs)* — see §10.1 below.

### 10.1 Consumption-stage variants & cooking energy — design decision needed

**Background.** The RIVM database models food in three stages:

| Stage | What it covers |
|---|---|
| `retail` | Production → store shelf. Impact "as bought". |
| `consumption` (logistics-only prep_methods: `no preparation`, `chilled at consumer`, `freezing at consumer`, `dilution`) | Adds home transport + household storage to the retail stage. No cooking energy. |
| `consumption` (cooking prep_methods: `boiling`, `pan frying`, `deep frying`, `water cooker`, `microwave`) | Adds home transport + cooking energy to the retail stage. |

**The problem.** When a caterer builds a meal with 5 cooked ingredients and selects `boiling` for each, the total cooking energy is summed 5×, as if each ingredient was boiled in a separate pot. In reality, one pot of boiling water heats everything.

**Note (2026-04-22):** Procurement mode has no cooking stage — only `distribution` variants — so this issue doesn't apply there. For Meal mode, the fix should follow RIVM's own methodology: review the RIVM background documents to understand how they model cooking energy per ingredient, then implement the same approach. Only then decide between per-ingredient vs meal-level cooking widgets. **Do not guess at cooking factors — use RIVM numbers directly.**

**Current status (P5).** Default variant is `retail` ("as bought") to give a clean, comparable baseline with no cooking overhead. Consumption variants are still selectable. Cooking variants show an amber warning; logistics-only consumption variants show a neutral note about home transport.

**Three options for a proper fix (deferred until RIVM docs reviewed):**

**Option A — Retail default + single meal-level cooking widget** *(recommended, pending doc review)*
- Meal list shows only retail-stage ingredients.
- Add a "Meal preparation" panel: select cooking method (none / boiling / pan frying / oven) + heat source (gas / induction / electric-NL-grid).
- Compute cooking energy once for the whole meal; add as a single line item in the footprint.
- Zero double-counting. Clean UX. Requires modelling cooking energy separately from RIVM rows.

**Option B — Per-ingredient consumption toggle with delta display**
- Retail stage is the default.
- User can flip an ingredient to its consumption variant; the card shows the **delta** vs retail ("+0.045 kg CO₂ for boiling").
- Helps answer "how much does cooking this ingredient cost?" but still technically double-counts if multiple items share a cooking vessel.

**Option C — Smart cooking-energy pooling**
- Detect multiple ingredients with the same cooking method; apply that method's overhead once (shared-vessel heuristic).
- Most accurate but complex to model and explain to users.

**Recommended path:** Option A. Build in P7 alongside procurement mode. The cooking widget sits at the bottom of the left panel in Meal mode; its footprint contribution appears as a special non-ingredient row in the right panel results.

### 10.2 Bar chart redesign — parked *(resolve before or during P8)*

**Current state.** `BarsView` renders 6 separate vertical sections (one per metric), each containing all ingredients sorted high→low by that metric. With even 4–5 ingredients this becomes very long — the user has to scroll past a wall of bars to get to the less-familiar metrics (acidification, eutrophication).

**The problem.** Six sections × N ingredients = 6N bar rows. Not scannable. The first metric (CO₂) dominates attention; the others are buried below the fold.

**Options to evaluate (pick one for P8):**

| Option | Description | Pros | Cons |
|---|---|---|---|
| A — Metric-selector dropdown | One section visible at a time; user picks which metric to inspect from a `<select>` | Minimal vertical space | Requires interaction to see other metrics |
| B — Stacked bar per ingredient | One row per ingredient, 6 coloured segments proportionally stacked | Compact; shows relative profile at a glance | Segments have different units — needs normalisation first |
| C — Compact 2-column grid | 3 metrics left, 3 right; each column shows a mini-bar chart | Reasonably compact without normalisation hacks | Slightly complex layout |
| D — Tabs per metric | Six tabs above the chart area | Clean; same vertical height always | Tabs can feel clunky with 6 options |

**Leaning toward:** Option A (dropdown) for simplicity, or D (tabs) to match the existing tab idiom. Decide when starting P8.

### 10.3 Radar chart — normalization & reference strategy *(resolve before or during P8)*

**Current state.** Each axis is normalised as `min(1, total / (AXIS_REFS[key] × totalMealKg))` where `AXIS_REFS` are p95 per-kg values from the actual RIVM DB. So a meal's polygon fills the radar if *every kilogram* of food is at the 95th-percentile worst product.

**The problem.** Real meals are diverse — a salad might have 20 g of olive oil (very high CO₂/kg) mixed with 200 g of lettuce (near-zero). The olive oil dominates per-kg but has tiny total contribution. The result: the radar polygon looks very small and gives a false "this meal is fine" impression even for meals with genuinely high-impact ingredients. Conversely, an ingredient like oil that is heavy per-kg but used in small amounts gets diluted.

**Root cause.** The reference is "worst-product-per-kg × total-meal-kg" — a theoretical all-worst-case meal at the same weight. That reference is almost impossible to hit in practice for a diverse meal, so polygons are always small.

**Options to evaluate (pick one for P8):**

| Option | Description | Notes |
|---|---|---|
| A — Per-ingredient vs its own product-group reference | Each ingredient normalised against the p95 value for its own RIVM productgroup; radar shows *relative badness within category* | Most meaningful for "is this a good chicken choice?" but complex; requires productgroup reference table |
| B — Typical-meal reference basket | Reference = median Dutch daily intake (e.g. 2000 kcal typical basket) rather than "all worst-case" | Gives intuitive "how does this meal compare to an average day?" framing; needs a reference basket definition |
| C — Absolute scale with per-axis labels | Drop the "fill = 100%" metaphor entirely; show absolute values on each axis with guideline rings labelled in real units | Honest but requires user to understand kg SO₂-eq |
| D — Keep current + add context label | Stick with current approach but add a note: "A filled polygon ≈ all ingredients at worst 5% of their kind" | Lowest effort; partially misleads |

**Leaning toward:** Option A or B. Decision needed before building P8 scoring view where the radar becomes the primary impact visual.

---

## 11. Things explicitly NOT doing (yet)

- Mobile apps. Web-responsive only.
- Public ingredient search. Everything behind login from P6 onwards.
- Editing RIVM data. Reference DB is read-only from the app.
- Complex recipe yield modelling (cooked weight, moisture loss).
- LCA methodology changes — we trust RIVM outputs as given.
- AI-powered ingredient extraction from free text.
- Carbon-offset purchasing integrations.

---

## 12. Key commands (updated per phase)

```
# Dev
docker compose up                                  # backend + postgres + frontend
backend$  alembic upgrade head                     # migrate user DB (P6+)
backend$  python scripts/ingest_rivm.py            # (P1) build reference.db — run via WSL on Windows
backend$  python scripts/ingest_nevo.py            # (P2) add nevo_nutrition
backend$  python -m pytest                         # run tests
backend$  uvicorn app.main:app --reload            # local API on :8000
frontend$ npm run dev
frontend$ npm run typecheck
```

**Ingest on Windows host:** SQLite on a `\\wsl$\...` UNC path deadlocks under Windows-native Python. Run ingest scripts via `wsl -d Ubuntu -- bash -lc ".venv/bin/python scripts/ingest_rivm.py"` from the `backend/` dir.

**API surface (as of P3+P2):**
- `GET /health`
- `GET /api/ingredients?mode={meal|procurement}&q=<term>&limit=10` → `{mode, query, results: [{primary_name, nevo_code, ..., score, variants: [{rivm_item_id, label, stage, prep_method, <metrics>}]}]}`
- `GET /api/rivm_item/{id}` → single item with full environmental metrics **and** `nutrition: {...}` (or `null`) joined from `nevo_nutrition` via `nevo_code`. Curated macros + micros plus full 148-column `raw_nutrients` JSON.

OpenAPI JSON at `/openapi.json`, Swagger UI at `/docs`.

---

*Full history in `CHANGELOG.md`.*
