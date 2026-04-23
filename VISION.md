# MiSt — Vision & Build Plan (v2)

> **Living document.** Every working session appends to the Changelog at the bottom and updates the relevant section above. Read this top-to-bottom on context loss.
>
> **Audience:** future-Claude (this CLI + VS Code), and Mrigank.

---

## 1. Product vision

MiSt is a **one-shot sustainability tool for caterers and food-service operators** in the Netherlands. One hosted app, multi-tenant, two modes:

- **Procurement mode** — bulk buy analysis (weekly/monthly purchase lists from distributors like Sligro). Answers: *how sustainable is our supply chain this period?* Aggregate CO₂, water, land, acidification, eutrophication; nutrient profile of what was bought; EAT-Lancet alignment score of the basket.
- **Meal mode** — per-dish analysis. Same metrics per meal, with variant selection (raw / supermarket / boiled / pan-fried / …), save/rank meals, EAT-Lancet score per meal.

**Sold as:** a hosted SaaS product. Customers log in, save history, export reports.

**Target user story:** a caterer (e.g. APEL buys from Sligro) uploads their weekly order list and gets a shareable sustainability report in one click; or their chef scores individual recipes during menu planning.

---

## 2. V1 inventory (snapshot of the MVP on `main` before v2 work starts)

One-file FastAPI app (`app.py`, ~1180 lines — routes, matching, scoring heuristics, and inline HTML/CSS/JS all in one place).

**Data**
- `rivm.db` — single SQLite table `consumption` from the *consumption* sheet of the RIVM environmental DB. 411 rows, 344 unique NEVO codes, cols: `name, nevo_code, co2_kgco2eq, so2_kg, p_kg, n_kg, land_m2a, water_m3`. No nulls in CO₂.
- `data/ingredients.csv` — 10-row local catalogue, **piece-weight hints + synonym attachments only** (never overrides RIVM footprints).
- `ingest_to_sqlite.py` — builds `rivm.db` from the RIVM Excel `tot-en-met-consumptie` sheet. Hard-coded WSL inbound path.

**Backend (all in `app.py`)**
- DataFrame loaded at boot; normalized search text + primary-name tiebreaker; token-stem matching via rapidfuzz; `PROCESSED_WORDS` penalty for overly-specific rows; boost for non-null CO₂.
- Routes: `GET /ingredient`, `POST /meal`, `POST /export` (CSV), `POST /missing` (coverage), `GET /` (UI).
- Unit conversion: `tools/metrics_engine.py` — g/kg/mg, ml/L at density 1, `piece` via piece-weight map (fallback 100 g).
- `MOCK_SAFE` flag at `app.py:107` as an emergency canned-response mode (off).

**Frontend (inline in `app.py:442-1176`)**
- Eaternity-inspired theme. DM Serif Display + DM Sans. Deep-green / cream / amber palette.
- Search → match cards → meal list with editable qty/unit. Three result views (Bars / Radar / Heatmap). Per-100 g toggle. Swap-to-lower-impact. CSV export. Client-side PNG report exporter (~200 lines of canvas drawing).

**Known limits**
1. Everything in one file.
2. No user persistence — meals aren't saved.
3. Matching brittle outside RIVM's Dutch-centric catalogue.
4. Unit heuristics thin (no cooked↔raw; no density lookup).
5. "Alternative" swap feature relies on a `productgroup` column that isn't preserved in the ingest → rarely fires.
6. No real tests. `tests/playwright/test_toggle.spec.js` targets stale UI.
7. `requirements.txt` pins future-ish versions (pandas 3.0.1, fastapi 0.135).

**Preserved as `legacy_app.py` when v2 restructure lands.**

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

## 13. Changelog

- **2026-04-23 · Claude (CLI) · Bug fixes — zero totals, sort, custom date range**
  - **Root cause fixed**: `list_meals` and `list_procurement` were manually constructing list-item schemas without passing the totals fields — they silently defaulted to `null` (rendered as `0` in dashboard; sort-by-metric had no effect because all values were equal-null).
  - **Fix**: all 6 totals (`total_co2_kg`, `total_water_m3`, `total_land_m2a`, `total_so2_kg`, `total_p_kg`, `total_n_kg`) now explicitly passed in both list endpoint constructors.
  - **`compute_totals_async`**: replaced synchronous `compute_totals(ref_session, ...)` call (cross-thread sync session in async route) with `asyncio.to_thread` wrapper that creates its own fresh session inside the worker thread. No more `ref_session` FastAPI dependency on the two create endpoints.
  - **Meal sort expanded**: all 6 env metrics now available as sort options, grouped with `<optgroup>` (CO₂, Water, Land use, Acidification SO₂, FW Eutrophication P, Mar. Eutrophication N — each high/low direction). Sort uses `-Infinity` sentinel for null values so records without totals always sort to the bottom.
  - **Procurement dashboard — custom date range**: "Custom" period pill added alongside 2W/1M/3M/1Y/All; when selected shows From/To `<input type="date">` inputs. Filtering is client-side over the already-fetched entries list.
  - **Procurement dashboard — removed trend chart**: "CO₂-eq per order" proportional bars section removed as per user feedback.
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
  - **Startup**: `_init_user_tables()` runs `metadata.create_all()` on boot with up-to-10 retries (handles Docker startup ordering). Alembic scaffold (`alembic.ini`, `alembic/env.py`) added for future production migrations.
  - **Meals API**: `GET /api/meals` (list, newest-first), `POST /api/meals` (create with inline ingredients), `GET /api/meals/{id}`, `DELETE /api/meals/{id}`. All endpoints require valid JWT.
  - `MealIngredient` stores `primary_name` snapshot so history renders without cross-DB joins. `rivm_item_id` kept for future "reload meal" feature.
  - **Frontend — AuthContext**: `useAuth()` hook; token persisted in `localStorage`; verifies stored token via `/auth/users/me` on app load; clears on 401.
  - **Login page**: email + password form with login/register toggle (no separate /register route). On success navigates to `/meal`.
  - **History page**: lists saved meals (name, date, ingredient count); delete with confirm dialog; "not logged in" and "empty" states.
  - **MealMode save section**: appears at bottom of results panel. Guest → "Sign in to save" + link. Logged-in → name input + save button. Success flash (3 s).
  - **Nav**: `nav-right` flex container with RIVM badge + user name + Sign out (logged-in) or Sign in button (guest).
  - `docker-compose.yml` updated: Postgres `healthcheck` (`pg_isready`); backend `depends_on: db: condition: service_healthy`.
  - `backend/.env.example` added for local dev without Docker.
  - Tests: 2 assertions updated to reflect P5 label changes (`"supermarket"` → `"as bought · Ambient"`, `"distribution"` → `"distribution · Ambient"`). All 13 pass.
  - **Exit criteria met**: register → log in → add ingredients → calculate → save meal → log out → log in → History shows meal.



Append newest-first. Each entry: date, author, one-line summary, links to any new sections.

- **2026-04-20 · Claude (CLI) · P4 complete — React frontend shell with routing and design system**
  - Design source: `MiSt-standalone.html` (Claude Design export, ~1.4 MB bundled) read via targeted grep extraction. Extracted exact tokens, layout dimensions, typography, spacing, and interaction patterns.
  - **Design decision — build a clean shell now:** Nav declares all future routes (Meal, Procurement, History, Login) so each new phase only adds a page component. Stub pages display a "Coming in PX" card rather than dead code. No pre-building of auth/history UI — those require the Postgres user DB which lands in P6.
  - `frontend/src/theme/global.css` — full rewrite with all design-system classes: nav (fixed 56px, deep-green), landing (hero + two mode cards 340px), split mode layout (left 390px fixed, right flex-1), search input with icon, ingredient cards with variant pill + qty/unit inputs, empty-state with diagonal-stripe icon, metric chips, results tabs, nutrition strip, EAT-Lancet score placeholder, stub pages.
  - `frontend/src/components/Nav.tsx` — fixed nav: back arrow (on non-landing routes, navigates home), MiSt serif logo, screen-tag pill (shows current mode name), RIVM amber badge.
  - `frontend/src/routes/Landing.tsx` — hero section (badge, 52px serif heading, subtext), two mode cards with SVG icons (PlateIcon, BoxIcon), hover animations (translateY -2px, border-color, shadow), "Start →" CTA buttons routing to `/meal` and `/procurement`, footer tagline.
  - `frontend/src/routes/MealMode.tsx` — full split layout shell: search input (with magnifier icon, focus state), empty ingredient list with hint text, disabled "Calculate meal footprint" button, empty-state right panel with bar chart icon + descriptive text. Ready to fill in P5.
  - `frontend/src/routes/ProcurementMode.tsx` — same split layout with period label bar (auto-calculates current ISO week), product search, empty list, disabled "Analyse procurement" button, basket-icon empty state. Ready for P7.
  - `frontend/src/routes/History.tsx` + `Login.tsx` — stub cards with phase labels.
  - `frontend/src/App.tsx` — `BrowserRouter` + `Routes` declaring `/`, `/meal`, `/procurement`, `/history`, `/login`. Nav rendered outside `<Routes>` so it's always visible.
  - TypeScript clean (`npm run typecheck` 0 errors). Vite boots in 203ms.
  - **Exit criteria met** (VISION §9 P4: React scaffold in place, theme tokens applied, landing with two mode buttons, clicking into Meal mode renders empty search UI). All future phases add to existing route files — no restructuring needed.

- **2026-04-20 · Claude (CLI) · Scoring fix + P2 complete — tiered ranking, NEVO nutrition ingest**

  **Search scoring — rebuilt per user feedback that "potato" was surfacing `Crisps potato` and `Sweet potato starch` above plain potato, and Dutch queries saturated the fuzzy tier:**
  - Rewrote `services/matching/search.py::_score_group` as a tiered ladder restored from v1: **exact string → 120**, **all query stems ⊆ candidate stems → 100 − length penalty − modifier penalty**, **partial stem overlap → 65 + 8·|overlap| − penalties**, **fuzzy fallback (token_set_ratio, then WRatio across primary+NL+EN names)**. Scores each of `primary_name`, `nevo_name_en`, `nevo_naam_nl` separately and takes the max — this is how Dutch `aardappel` now resolves via NL name.
  - **Bug fix:** v1's `PROCESSED_WORDS` blocklist contained plural forms (`crisps`, `nuggets`, `flakes`) but I was stemming candidate tokens to singular before checking membership — penalty never fired. Pre-stem the blocklist at module init. Also added `ketchup`, removed prep-method-masquerading entries (`mashed`, `pre-fried`, `prepared`).
  - **New tiebreaker:** `primary_leads` (True iff the primary name's first word stem is in the query stems). RIVM names foods head-noun-first, so this cleanly demotes oddities like `Eggs chicken` for query `chicken` without touching score tiers. Sort order: `score desc → primary_leads → shorter primary_name`.
  - **v1 features preserved (not rebuilt):** `_stem` suffix stripper (ies/es/s), `PROCESSED_WORDS` concept, prefer-generic-over-specific tiebreak, normalize→ASCII→lowercase→space-only.
  - `backend/scripts/validate_search.py` — debug harness; runs potato/tomato/chicken/onion/oil/cheese/aardappel across both modes against the live `reference.db` and prints top-5 with scores. Ran it; results look sane: plain `Tomato` exact → 120, `Tomato sauce` → 69, `Potato starch` demoted to 73, `Chicken fillet` ranks above `Eggs chicken` on `primary_leads`.

  **P2 — NEVO nutrition ingest (same database as RIVM):**
  - Confirmed VISION §4.1 design: one SQLite file, `data/reference.db`, holding both `rivm_item` (P1) and now `nevo_nutrition` (P2). User data → separate Postgres at P6.
  - `backend/app/models/reference.py` — added `NevoNutrition` ORM model. PK `nevo_code`. Curated typed fields for kJ/kcal, all macros (protein + plant/animal split, fat + sat/mono/poly, carb/sugar/starch/fibre, alcohol), curated minerals (Na, Ca, Fe, Vit C, Vit D). **Lossless** `raw_nutrients: JSON` holds all 148 original columns verbatim.
  - `backend/scripts/ingest_nevo.py` — reads `data/source/NEVO2025_v9.0.xlsx` sheet `NEVO2025` (header row 0), maps 20 curated columns via `CURATED_COLUMNS` dict, dumps every row to `raw_nutrients` as a JSON-safe dict (NaN → None, floats preserved, rest stringified). Drops+recreates **only** the `nevo_nutrition` table; `rivm_item` untouched. Safe to re-run.
  - Ingest run: **2328 rows inserted**, 100% have kcal + protein_g, **331 of 344 distinct RIVM NEVO codes (96.2%) joinable to nutrition**. Exit criterion from VISION §9 P2 met.
  - `backend/app/schemas/ingredient.py` — added `NevoNutritionOut` (all curated fields + `raw_nutrients: dict[str, Any] | None`). `RivmItemDetail` now carries optional `nutrition: NevoNutritionOut | None`.
  - `backend/app/api/ingredients.py::get_rivm_item` — after loading `RivmItem`, looks up `NevoNutrition` by `nevo_code` and attaches. Returns `nutrition: null` when no match (expected for the 3.8% of RIVM rows without nutrition coverage, and for any row where `nevo_code is None`).
  - Tests extended: `conftest.py` seeds a `NevoNutrition` row for nevo_code=200 (Potato) but not 100 (Sweet potatoes). `test_ingredients.py` adds `test_detail_includes_nutrition_when_nevo_matched` (asserts english_name, kcal, protein_g, and lossless `raw_nutrients`) and `test_detail_nutrition_null_when_no_nevo_match`. **All 13 tests pass.**
  - Smoke-tested live: `/api/rivm_item/531` (retail Tomato, nevo=2735) returns `english_name='Tomato av boiled', kcal=23.0, protein_g=0.7 (plant 0.7, animal 0.0), fat_g=0.7 (sat 0.1), carb_g=2.9, fibre_g=1.3, sodium_mg=2.0, vitamin_c_mg=14.0, raw_nutrients=148 cols`.

  **Exit criteria met** — scoring demonstrates plain foods beat processed variants across 7 query axes in both modes; nutrition lookup works for any NEVO code joinable between the two tables.

- **2026-04-19 · Claude (CLI) · P3 complete — ingredient search API with grouped variants**
  - `backend/app/schemas/ingredient.py` — Pydantic v2 response models: `IngredientVariant`, `IngredientGroup`, `IngredientSearchResponse`, `RivmItemDetail`. All ORM-attribute-compatible via `model_config = ConfigDict(from_attributes=True)`.
  - `backend/app/services/matching/search.py` — `search_ingredients(session, mode, query, limit)` returns a list of `ScoredGroup`. Normalises query (lowercase, strip diacritics, punctuation → space), filters `rivm_item` by mode-specific stages (`meal` → retail+consumption, `procurement` → distribution), groups by NEVO code (falling back to lowercased `primary_name` when NEVO is null), scores each group with `rapidfuzz.WRatio` against `primary_name + nevo_name_en + nevo_naam_nl`, drops results below `MIN_SCORE=40`, sorts score desc then shorter primary_name asc. `variant_label(row)` emits `distribution` / `supermarket` / `<prep_method>` / `unspecified`. Variants within a group sorted retail-before-consumption then by prep method.
  - `backend/app/api/ingredients.py` — `GET /api/ingredients?mode=&q=&limit=` and `GET /api/rivm_item/{id}`. Uses `get_reference_session` dep. Query validation via FastAPI `Query(..., pattern=...)` and `min_length=1` (empty query → 422, unknown mode → 422).
  - `backend/app/main.py` — includes `ingredients_router`. OpenAPI auto-generated at `/openapi.json` / `/docs`.
  - **Matching simplification vs v1:** v1's `PROCESSED_WORDS` penalty and CO₂-coverage boost existed to suppress noisy variant rows inside a single flat result list. v2 surfaces variants *explicitly* (grouped-variant picker), so the retrieval layer only has to find the right *group* — simpler `WRatio` over primary+NEVO names is enough. If retrieval quality slips in practice we can reintroduce heuristics per-phase.
  - **Tests:** `backend/tests/conftest.py` spins up an in-memory SQLite with `StaticPool + check_same_thread=False` (required so FastAPI's per-request session sees the same DB as the setup code), seeds 7 RivmItem rows across all 3 stages, overrides `get_reference_session`. `backend/tests/test_ingredients.py` covers meal-mode grouping (retail+2×consumption under one NEVO), procurement-mode single-variant shape, ranking, query/mode validation (422), detail endpoint, 404. 8 tests, all green (`.venv/bin/python -m pytest -q`).
  - **Smoke-tested against committed `reference.db`:** `mode=meal q='sweet potato'` → top group `Sweet potatoes nevo=2112 score=90` with variants `[supermarket, boiling, pan frying]`. `mode=procurement q='chicken'` → top two groups `Chicken fillet`, `Chicken, w skin`, each with a single `distribution` variant.
  - **Exit criteria met** (VISION §9 P3: modular backend, `/api/ingredients` with grouped variants, OpenAPI auto-generated). Note: legacy `/meal`, `/export`, `/missing` endpoints NOT yet ported — those flows land in P5 when the new React UI is wired up; `legacy_app.py` remains runnable in parallel until then.

- **2026-04-19 · Claude (CLI) · P1 complete — RIVM ingestion (all 3 stages)**
  - `backend/app/db/base.py` — shared `DeclarativeBase` for reference-DB models.
  - `backend/app/db/reference_session.py` — `reference_engine` + `ReferenceSession` factory + `get_reference_session()` FastAPI dep.
  - `backend/app/models/reference.py` — `RivmItem` ORM (stage, nevo_code, parsed fields primary_name/prep_method/packaging/conditions, raw_name, NL+EN NEVO labels, all 6 env metrics; indexes on stage/nevo_code/primary_name).
  - `backend/app/config.py` — switched `DEFAULT_REFERENCE_DB` to absolute path (`Path(__file__).resolve().parents[1] / ../data/reference.db`) so ingest + app + Docker agree regardless of CWD.
  - `backend/scripts/ingest_rivm.py` — reads all three stage sheets from `data/source/Database milieubelasting*.xlsx`, drops+recreates `data/reference.db`, parses pipe-delimited names per stage (distribution → `prep_method=None`; retail → `prep_method='supermarket'`; consumption → lowercased method word), preserves `raw_name` verbatim, tolerates missing NEVO codes, prints per-stage verification counts.
  - Ran ingest via WSL-side Python (`wsl -d Ubuntu -- bash -lc ".venv/bin/python scripts/ingest_rivm.py"`). Windows-native Python against `\\wsl$\Ubuntu\...\data\reference.db` fails with SQLite "database is locked" on UNC paths — must run ingestion inside WSL.
  - Verification: `distribution rows=376 unique_nevo=330 with_co2=376 · retail rows=376 unique_nevo=330 with_co2=376 · consumption rows=411 unique_nevo=344 with_co2=411`. Spot-checks confirm clean parsed fields (retail rows all `supermarket`; distribution all null; consumption varies over boiling/pan frying/deep frying/microwave/chilled at consumer/no preparation/dilution/freezing at consumer/water cooker + a handful with null).
  - **Exit criteria met** (VISION §9 P1: counts 376/376/411, all 6 metrics preserved, raw + parsed names both stored). Legacy app untouched in `legacy/` and still boots against `legacy/rivm.db`.

- **2026-04-19 · Claude (CLI) · P0 complete — repo restructure**
  - v1 files moved to `legacy/` (legacy_app.py, legacy_ingest.py, mock_server.py, inspect_spreadsheet.py, rivm.db, Procfile, requirements.txt, tools/, tests/playwright/, verify/, data/ingredients.csv). Legacy app still runs self-contained from `legacy/`.
  - Source xlsx files (RIVM env + NEVO2025) moved to `data/source/` (gitignored).
  - `backend/` scaffold: pyproject.toml (fastapi, sqlalchemy, alembic, psycopg, pandas, rapidfuzz, openpyxl), Dockerfile, minimal FastAPI app exposing `GET /health`, config via pydantic-settings, empty package tree for api/services/models/schemas/db.
  - `frontend/` scaffold: Vite + React 18 + TS, theme tokens + global.css lifted from v1 (cream bg, deep green, DM Serif + DM Sans), landing stub `App.tsx`.
  - Root: `docker-compose.yml` (postgres + backend + frontend), `railway.json` (Dockerfile deploy), `.gitignore` rewritten, `README.md` rewritten with quickstart.
  - Smoke tests: Python AST-parses clean across `backend/app/` and `backend/tests/`; JSON files valid. Not yet booted — user to verify with `docker compose up` or local uvicorn+vite.
  - Known quirk: top-level `node_modules/` directory from v1 could not be removed from WSL (Windows file lock). Gitignored, harmless, will vanish if deleted externally.
  - **Exit criteria met.** Backend and frontend scaffolds exist, v1 preserved, deploy configs ready.

- **2026-04-22 · Claude (CLI) · P5 complete — frontend connected to backend**
  - `src/api/types.ts` — TypeScript interfaces mirroring all backend Pydantic schemas; local `MealItem`, `Unit`, `MetricKey` types.
  - `src/api/client.ts` — `searchIngredients()` + `getRivmItem()` using relative base URL (blank) so Vite's `/api` proxy forwards requests to the backend inside WSL2.
  - `src/hooks/useDebounce.ts` — 280 ms debounce hook.
  - `src/utils/units.ts` — `toKg()` (RIVM: per kg) + `portions100g()` (NEVO: per 100 g).
  - `src/components/IngredientSearch.tsx` — live debounced search dropdown with loading/error/no-results states; NEVO English name shown as subtitle to distinguish same-name groups (e.g. "Tomato av raw" vs "Tomato av boiled"); error state surfaces network failures visibly.
  - `src/components/MealItemCard.tsx` — variant picker (select when >1), qty+unit inputs; CO₂ hint label corrected to `/ kg`; consumption-stage variants show amber cooking warning (only for actual cooking methods) or a grey logistics note (no preparation / chilled / frozen).
  - `src/components/MetricChips.tsx`, `BarsView.tsx`, `HeatmapView.tsx` — **unit bug fixed**: all RIVM calculations now use `toKg()` (data is per kg), not `portions100g()`. Previous code overcounted by 10×.
  - `src/components/RadarView.tsx` — **normalization fixed**: each axis independently normalised against a p95 reference value calibrated to the actual RIVM DB (`co2=14 kg/kg`, `so2=0.053`, `p=0.0053`, `n=0.017`, `land=12 m²a`, `water=0.35 m³`). Previously collapsed to a single spike because a global max was applied across all 6 different-scale metrics.
  - `src/components/NutritionStrip.tsx` — kcal / protein / fat / carbs / fibre totals from NEVO 2025; uses `portions100g()` (NEVO is per 100 g — correct).
  - `src/routes/MealMode.tsx` — full implementation: live state, retail-first default on add, Calculate button, 3-tab chart view, PNG export (html2canvas, lazy-loaded). Export button hidden before capture and restored after so it doesn't appear in the image.
  - `backend/app/services/matching/search.py` — `variant_label()` rewritten: `"supermarket"` → `"as bought"`; packaging appended with `·` separator when packaging ≠ "Not packed" (fixes spinach showing 3× duplicate labels for Food can vs Glass jar variants).
  - `src/vite-env.d.ts` — added to expose `import.meta.env` types to TypeScript.
  - **Proxy fix**: Vite proxy (`/api → http://localhost:8000`) was already in `vite.config.ts` but `client.ts` was using a hard-coded full URL, bypassing the proxy and hitting a cross-origin network error from Windows browser → WSL2 backend. Fixed by defaulting BASE to `''` (relative).
  - **Open design decision documented in §10.1**: cooking double-count problem parked; Option A (retail-only + single meal-level cooking widget) recommended for P7.

- **2026-04-19 · Claude (CLI) · Vision created**
  Captured v1 inventory (§2), confirmed data sources (§3 — RIVM 3 stages 376/376/411, NEVO 2328×148), laid out v2 schema (§4), grouped-variant UX (§5), EAT-Lancet scoring from guide (§6), chose React/Vite/TS + FastAPI + SQLite-reference + Postgres-Railway (§7.1), preserved v1 design tokens (§8), phased delivery P0–P10 (§9). Decisions: auth deferred to P6; procurement MVP = name + quantity only; EAT-Lancet bucketing built from scratch; single multi-tenant app.
