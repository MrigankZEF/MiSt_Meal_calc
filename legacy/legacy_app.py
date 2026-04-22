from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from pathlib import Path
import pandas as pd
from rapidfuzz import process, fuzz

from fastapi.responses import JSONResponse
import math

def _sanitize(obj):
    # recursively replace NaN/NaT with None and convert numpy scalars
    if obj is None:
        return None
    # basic types
    if isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int,)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj):
            return None
        return obj
    # pandas/numpy types handled via duck-typing
    try:
        import numpy as _np
        if isinstance(obj, _np.generic):
            py = obj.item()
            return _sanitize(py)
    except Exception:
        pass
    # dict
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k,v in obj.items()}
    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    # fallback: try to coerce via str
    try:
        return str(obj)
    except Exception:
        return None

def sanitize_for_json(payload):
    try:
        return _sanitize(payload)
    except Exception:
        return payload



def sanitize_row(rowdict):
    import pandas as _pd
    out = {}
    for k,v in rowdict.items():
        try:
            if _pd.isna(v):
                out[k]=None
            else:
                # numpy/pandas scalars
                try:
                    out[k] = v.item()
                except Exception:
                    out[k] = v
        except Exception:
            out[k] = v
    return out


DB = Path('rivm.db')
if not DB.exists():
    raise SystemExit('DB not found; run ingest')

df = pd.read_sql('SELECT * FROM consumption', f'sqlite:///{DB}')
# Column heuristics: find CO2 column
cols = df.columns.tolist()
co2_col = None
for c in cols:
    if 'co2' in c.lower() or 'global warming' in c.lower():
        co2_col = c
        break
if co2_col is None:
    raise SystemExit('CO2 column not found in table')

# canonical display names (first column values)
names = df[cols[0]].astype(str).tolist()

# allow a small local curated catalog to be merged into the dataset
from tools.data_curator import load_local_catalog
local_df = load_local_catalog()
# local curated catalog loaded; we'll merge synonyms into existing RIVM rows after building search texts
piece_weights = {}
if not local_df.empty:
    # build piece weight map (populate later when synonyms are attached)
    for _, r in local_df.iterrows():
        try:
            nm = str(r.get('name','')).strip()
            if not nm or nm.lower()=='nan':
                continue
            if 'piece_g' in r and pd.notna(r.get('piece_g')):
                piece_weights[nm.lower()] = float(r.get('piece_g'))
        except Exception:
            pass


app = FastAPI()
# TEMPORARY MOCK SAFE MODE: enable to unblock UI while robust fixes continue
MOCK_SAFE = False

# ---- matching improvements: build search candidates and normalizer ----
import re
import unicodedata

def normalize_text(s: str) -> str:
    if s is None:
        return ''
    s = str(s).lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9\s]", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # simple plural heuristic: remove trailing s for single-word queries
    return s

# build a per-row search text composed of multiple useful fields
search_texts = []
primary_names_norm = []
candidate_token_counts = []
for i, row in df.iterrows():
    parts = []
    # prefer 'name' if present, else first column
    raw_name = row.get('name','') if 'name' in df.columns else row.iloc[0]
    # the dataset stores long descriptors separated by '|' — keep the primary token (before '|') for matching
    primary = str(raw_name).split('|')[0].strip()
    parts.append(primary)
    # add NEVO name/productgroup if present
    for c in ['NEVO name', 'NEVO naam', 'NEVO_name', 'NEVO_naam', 'NEVO productgroup', 'NEVO productgroup', 'NEVO productgroup']:
        if c in df.columns:
            parts.append(row.get(c,''))
    # also add the numeric NEVO code as string
    if 'nevo_code' in df.columns:
        parts.append(str(row.get('nevo_code','')))
    combined = ' '.join([str(p) for p in parts if p and str(p).strip()])
    # ensure combined starts with the primary short name
    combined = primary + ' ' + combined
    norm = normalize_text(combined)
    search_texts.append(norm)
    # primary name normalization (for tie-breakers) — only the first part
    pname = normalize_text(primary)
    primary_names_norm.append(pname)
    candidate_token_counts.append(len(norm.split()))

# names as originally displayed (non-normalized)candidate_token_map = {}  # index -> list of extra synonym tokens
# attach local synonyms to existing RIVM rows (do not create new rows)
if not local_df.empty:
    try:
        for _, r in local_df.iterrows():
            lname = str(r.get('name','')).strip()
            if not lname:
                continue
            lqn = normalize_text(lname)
            # find a best authoritative candidate among existing search_texts
            try:
                best = process.extractOne(lqn, search_texts, scorer=fuzz.WRatio)
            except Exception:
                best = None
            if best:
                matched_text, score, idx = best
                if score >= 65:
                    # attach the raw local name token to that index so future searches match it
                    search_texts[idx] = search_texts[idx] + ' ' + lqn
                    candidate_token_counts[idx] = len(search_texts[idx].split())
                    # map piece weight under the canonical name
                    try:
                        canon = names[idx]
                        if 'piece_g' in local_df.columns and not pd.isna(r.get('piece_g')):
                            piece_weights[canon.lower()] = float(r.get('piece_g'))
                    except Exception:
                        pass
    except Exception:
        pass


# helper to score and choose best match with extra heuristics
from rapidfuzz import fuzz, process

# words that indicate a processed variant — penalise when query doesn't contain them
PROCESSED_WORDS = {
    'starch','nugget','nuggets','crisps','chips','schnitzel','mashed','pilsner',
    'buttermilk','sandwich','prepared','pre-fried','powder','extract','juice',
    'sauce','soup','paste','spread','cream','yoghurt','yogurt','pudding',
    'cake','biscuit','bread','roll','pasta','noodle','coconut',
}

def _stem(token):
    """Strip common plural/verb suffixes for fuzzy token matching."""
    for suffix in ('ies', 'es', 's'):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[:-len(suffix)]
    return token

def best_n_matches(query: str, n=3):
    qn = normalize_text(query)
    query_tokens = set(qn.split())
    query_stems = {_stem(t) for t in query_tokens}
    results = []

    # Score each candidate against the PRIMARY name only (text before first '|')
    # This prevents long RIVM descriptors from distorting the match.
    for idx, pname in enumerate(primary_names_norm):
        pname_tokens = set(pname.split())
        pname_stems = {_stem(t) for t in pname_tokens}

        # Exact full primary-name match
        if pname == qn:
            sc = 120
            results.append((idx, sc))
            continue

        # All query stems present in primary name stems
        if query_stems and query_stems.issubset(pname_stems):
            sc = 95
            extra_stems = pname_stems - query_stems
            if extra_stems & PROCESSED_WORDS:
                sc -= 25
            results.append((idx, sc))
            continue

        # Any query stem overlaps primary name stems
        overlap = query_stems & pname_stems
        if overlap:
            sc = 60 + len(overlap) * 8
            extra_stems = pname_stems - query_stems
            if extra_stems & PROCESSED_WORDS:
                sc -= 20
            results.append((idx, sc))
            continue

        # Fuzzy score against primary name only (not the full long string)
        ratio = fuzz.token_set_ratio(qn, pname)
        if ratio >= 70:
            sc = int(ratio * 0.75)
            extra_stems = pname_stems - query_stems
            if extra_stems & PROCESSED_WORDS:
                sc -= 15
            results.append((idx, sc))

    # Boost rows that actually have CO2 data; penalise missing
    boosted = []
    for idx, sc in results:
        try:
            if pd.notna(df.iloc[idx].get(co2_col)):
                sc = min(130, sc + 10)
            else:
                sc = max(0, sc - 30)
        except Exception:
            pass
        boosted.append((idx, sc))

    # collapse by best score per index
    best_by_idx = {}
    for idx, sc in boosted:
        if idx not in best_by_idx or sc > best_by_idx[idx]:
            best_by_idx[idx] = sc

    # sort: score desc, then fewest primary-name tokens (simpler = more generic)
    primary_token_counts = [len(pn.split()) for pn in primary_names_norm]
    items = sorted(best_by_idx.items(), key=lambda kv: (-kv[1], primary_token_counts[kv[0]]))
    out = []
    for idx, sc in items[:n]:
        rowdict = sanitize_row(df.iloc[idx].to_dict())
        out.append({'idx': idx, 'name': names[idx], 'score': min(100, int(sc)), 'row': rowdict})
    return out

from pathlib import Path


class Ingredient(BaseModel):
    name: str
    amount: float
    unit: str = 'g'

class Meal(BaseModel):
    items: list[Ingredient]

@app.get('/ingredient')
def get_ingredient(name: str):
    if MOCK_SAFE:
        q = name.lower()
        canned = [
            {'name':'potato', 'score':95},
            {'name':'sweet potatoes', 'score':78},
            {'name':'mashed potato', 'score':60},
        ]
        return JSONResponse(content={'matches': canned})
    matches = best_n_matches(name, n=5)
    if not matches or matches[0]['score'] < 40:
        raise HTTPException(status_code=404, detail=f'No good match (best score {matches[0]["score"] if matches else 0})')
    out = [{'name': m['name'], 'score': m['score']} for m in matches]
    return JSONResponse(content=sanitize_for_json({'matches': out}))

# Build a lookup dict for O(1) exact-name resolution
_name_to_idx = {name: i for i, name in enumerate(names)}

def compute_meal_items(items):
    total_co2 = 0.0
    details = []
    for it in items:
        req_name = it['name']
        # Exact match first: if the caller passes back the full RIVM name string,
        # use that row directly — no fuzzy re-matching that could pick the wrong row.
        if req_name in _name_to_idx:
            idx = _name_to_idx[req_name]
            best_name = req_name
            score = 100
        else:
            matches = best_n_matches(req_name, n=5)
            if not matches:
                details.append({'requested': req_name, 'error': 'no match'})
                continue
            best = matches[0]
            best_name = best['name']
            score = best['score']
            idx = best['idx']
        row = df.iloc[idx]
        perkg = float(row[co2_col]) if pd.notna(row[co2_col]) else 0.0
        # optional extra metrics if present
        water_col = None
        land_col = None
        for c in df.columns:
            lc = str(c).lower()
            if 'water' in lc and water_col is None:
                water_col = c
            if ('land' in lc or 'm2a' in lc) and land_col is None:
                land_col = c
        perkg_water = float(row[water_col]) if water_col and pd.notna(row[water_col]) else None
        perkg_land = float(row[land_col]) if land_col and pd.notna(row[land_col]) else None
        # convert amount to kg (use metrics_engine)
        from tools.metrics_engine import convert_to_kg
        kg = convert_to_kg(it.get('amount',0), it.get('unit','g'), best_name, piece_weights)
        contrib = perkg * kg
        total_co2 += contrib
        details.append({'requested': it['name'], 'matched': best_name, 'score': score, 'perkg': perkg, 'kg': kg, 'contrib': contrib, 'perkg_water': perkg_water, 'perkg_land': perkg_land})
    # find simple alternatives: same NEVO productgroup with lower perkg (best effort)
    pg_cols = [c for c in df.columns if 'productgroup' in str(c).lower()]
    for d in details:
        alt = None
        try:
            rowidx = df.index[df[names[0]]==d.get('matched')][0]
        except Exception:
            rowidx = None
        if pg_cols and rowidx is not None:
            pg = None
            pcol = None
            for pcol in pg_cols:
                pg = df.iloc[rowidx].get(pcol)
                if pg:
                    break
            if pg and pcol is not None:
                candidates = df[df[pcol]==pg]
                try:
                    cand = candidates[candidates[co2_col] < d.get('perkg', 9999)].sort_values(co2_col).iloc[0]
                    alt = {'name': str(cand[names[0]]), 'perkg': float(cand[co2_col]), 'delta': d.get('perkg',0)-float(cand[co2_col])}
                except Exception:
                    alt = None
        d['alternative'] = alt
    return {'total_co2_kgCO2eq': total_co2, 'details': details}

@app.post('/meal')
def calc_meal(meal: Meal):
    if MOCK_SAFE:
        items = [{'name': it.name, 'amount': it.amount, 'unit': it.unit} for it in meal.items]
        total = 0.0
        details = []
        for it in items:
            kg = float(it.get('amount',0)) / 1000.0
            contrib = round(0.2 * kg, 4)
            total += contrib
            details.append({'requested': it.get('name'), 'matched': it.get('name'), 'score': 90, 'contrib': contrib})
        return JSONResponse(content={'total_co2_kgCO2eq': round(total,4), 'details': details})
    items = [{'name': it.name, 'amount': it.amount, 'unit': it.unit} for it in meal.items]
    out = compute_meal_items(items)
    total = float(out.get('total_co2_kgCO2eq') or 0.0)
    details = []
    for d in out.get('details',[]):
        details.append({
            'requested': d.get('requested'),
            'matched': d.get('matched'),
            'score': int(d.get('score') or 0),
            'contrib': float(d.get('contrib') or 0.0),
            'perkg': float(d['perkg']) if d.get('perkg') is not None else None,
            'kg': float(d['kg']) if d.get('kg') is not None else None,
            'perkg_water': float(d['perkg_water']) if d.get('perkg_water') is not None else None,
            'perkg_land': float(d['perkg_land']) if d.get('perkg_land') is not None else None,
            'alternative': d.get('alternative'),
        })
    return JSONResponse(content=sanitize_for_json({'total_co2_kgCO2eq': total, 'details': details}))

@app.post('/export')
def export_meal(meal: Meal):
    items = [{'name': it.name, 'amount': it.amount, 'unit': it.unit} for it in meal.items]
    out = compute_meal_items(items)
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['requested','matched','score','contrib'])
    for d in out.get('details',[]):
        w.writerow([d.get('requested'), d.get('matched'), d.get('score') or '', d.get('contrib') or ''])
    return Response(content=buf.getvalue(), media_type='text/csv')

@app.post('/missing')
def missing_report(payload: dict):
    # payload: {items: [ {name: 'potatoes'}, ... ] }
    items = payload.get('items', [])
    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail='items must be a list')
    missing = []
    for it in items:
        name = it.get('name') if isinstance(it, dict) else str(it)
        if not name:
            continue
        matches = best_n_matches(name, n=1)
        if not matches:
            missing.append({'requested': name, 'reason': 'no match'})
            continue
        # try to find an authoritative RIVM row containing the normalized query and with a non-null CO2 footprint
        qn = normalize_text(name)
        found = False
        for _, crow in df.iterrows():
            try:
                rname = str(crow.get(cols[0], ''))
            except Exception:
                rname = ''
            if qn and qn in normalize_text(rname) and pd.notna(crow.get(co2_col)):
                found = True
                break
        if not found:
            # fallback: report the best match (if any)
            missing.append({'requested': name, 'matched': matches[0]['name']})
    return JSONResponse(content=sanitize_for_json({'missing': missing}))

# Demo UI — Eaternity-themed
@app.get('/')
def ui():
    html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MiSt MealCalc</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#F5F2EA;--bg-alt:#EAE6DA;--surface:#FFFFFF;
  --green-deep:#1A3A2A;--green-mid:#2D6A4F;--green-bright:#52B788;
  --green-light:#B7E4C7;--green-pale:#D8F3DC;
  --amber:#D4A017;--amber-light:#F4E4B0;
  --text:#1A1A18;--muted:#5A5A50;--hint:#9A9A8A;
  --border:rgba(26,58,42,0.15);--border-strong:rgba(26,58,42,0.30);
  --red:#E8523A;
  --r:6px;--r-lg:12px;
}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}

/* NAV */
.nav{background:var(--green-deep);padding:12px 24px;display:flex;align-items:center;justify-content:space-between}
.nav-logo{font-family:'DM Serif Display',serif;color:#fff;font-size:18px;letter-spacing:.01em}
.nav-tag{font-size:11px;font-weight:600;background:var(--green-bright);color:var(--green-deep);padding:4px 12px;border-radius:20px}

/* LAYOUT */
.page{max-width:1080px;margin:0 auto;padding:24px 16px;display:grid;grid-template-columns:1fr 380px;gap:20px;align-items:start}
@media(max-width:800px){.page{grid-template-columns:1fr}}

/* PANELS */
.panel{background:var(--surface);border-radius:var(--r-lg);border:.5px solid var(--border);padding:20px}
.panel-title{font-family:'DM Serif Display',serif;font-size:18px;color:var(--green-deep);margin-bottom:16px}
.section-label{font-size:10px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--hint);margin-bottom:10px;padding-bottom:6px;border-bottom:.5px solid var(--border)}

/* SEARCH */
.search-row{display:flex;gap:8px;margin-bottom:14px}
.search-input{flex:1;font-family:'DM Sans',sans-serif;font-size:13px;padding:9px 12px;border-radius:var(--r);border:.5px solid var(--border-strong);background:var(--surface);color:var(--text);outline:none}
.search-input:focus{border-color:var(--green-bright)}
.btn{font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;border:none;border-radius:var(--r);padding:9px 16px;cursor:pointer;transition:opacity .15s}
.btn:hover{opacity:.85}
.btn-primary{background:var(--green-mid);color:#fff}
.btn-ghost{background:transparent;color:var(--muted);border:.5px solid var(--border-strong)}
.btn-accent{background:var(--amber);color:var(--green-deep)}
.btn-danger{background:transparent;color:var(--red);border:.5px solid rgba(232,82,58,.3);font-size:11px;padding:4px 10px;border-radius:4px}
.btn-sm{font-size:11px;padding:5px 12px;border-radius:4px}

/* MATCH CARDS */
.match-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:4px}
@media(max-width:600px){.match-grid{grid-template-columns:1fr}}
.match-card{background:var(--bg);border:.5px solid var(--border);border-radius:var(--r);padding:10px 12px;cursor:pointer;transition:border-color .15s,background .15s;text-align:left;width:100%}
.match-card:hover{border-color:var(--green-bright);background:#EAF5EE}
.match-card.selected{border-color:var(--green-mid);background:var(--green-pale)}
.match-card-name{font-size:13px;font-weight:600;color:var(--green-deep);line-height:1.3;margin-bottom:3px}
.match-card-detail{font-size:10px;color:var(--hint);line-height:1.4}
.match-score{display:inline-block;font-size:9px;font-weight:600;letter-spacing:.06em;background:var(--green-pale);color:var(--green-mid);padding:1px 6px;border-radius:10px;margin-top:4px}

/* MEAL LIST */
.meal-item{display:flex;align-items:center;gap:8px;padding:10px 12px;background:var(--bg);border-radius:var(--r);border:.5px solid var(--border);margin-bottom:6px}
.meal-item-name{flex:1;font-size:13px;font-weight:500;color:var(--text)}
.meal-item-name-detail{font-size:10px;color:var(--hint)}
.meal-item-controls{display:flex;align-items:center;gap:6px;flex-shrink:0}
.qty-input{width:64px;font-family:'DM Sans',sans-serif;font-size:13px;padding:5px 8px;border-radius:4px;border:.5px solid var(--border-strong);background:var(--surface);color:var(--text);text-align:right}
.unit-select{font-family:'DM Sans',sans-serif;font-size:12px;padding:5px 6px;border-radius:4px;border:.5px solid var(--border-strong);background:var(--surface);color:var(--text)}
.meal-empty{text-align:center;padding:24px 0;color:var(--hint);font-size:13px}

/* TOTALS CHIPS */
.chips{display:flex;gap:8px;margin:14px 0}
.chip{flex:1;background:var(--green-deep);color:#fff;border-radius:var(--r);padding:10px 12px;text-align:center}
.chip-val{font-family:'DM Serif Display',serif;font-size:20px;color:var(--green-light);line-height:1}
.chip-lbl{font-size:9px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:rgba(255,255,255,.45);margin-top:3px}

/* RESULT CARDS — shared */
.result-card{padding:10px 12px;border-radius:var(--r);border:.5px solid var(--border);margin-bottom:8px;background:var(--surface)}
.result-card-header{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.result-card-name{font-size:13px;font-weight:600;color:var(--text)}
.result-card-contrib{font-size:13px;font-weight:600;color:#E24B4A}
.alt-row{margin-top:8px;padding-top:8px;border-top:.5px solid var(--border);display:flex;align-items:center;justify-content:space-between;font-size:11px;color:var(--muted)}
.alt-name{font-weight:500;color:var(--green-mid)}

/* Option A — stacked proportion bar */
.stack-row{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.stack-label{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--hint);width:52px;flex-shrink:0}
.stack-bar-wrap{flex:1;height:10px;border-radius:5px;background:#EDEBE3;overflow:hidden;display:flex}
.stack-seg{height:100%;transition:width .5s ease}
.stack-val{font-size:11px;font-weight:600;color:var(--muted);width:72px;text-align:right;white-space:nowrap;flex-shrink:0}

/* Option B — radar/spider chart */
.radar-wrap{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-start}
.radar-card{flex:1;min-width:140px;background:var(--bg);border-radius:var(--r);border:.5px solid var(--border);padding:8px;text-align:center}
.radar-name{font-size:11px;font-weight:600;color:var(--text);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.radar-canvas-wrap{position:relative;display:inline-block}

/* Option C — heatmap grid */
.heatmap-table{width:100%;border-collapse:collapse;font-size:12px}
.heatmap-table th{font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--hint);padding:6px 8px;text-align:center;border-bottom:.5px solid var(--border)}
.heatmap-table th:first-child{text-align:left}
.heatmap-table td{padding:7px 8px;text-align:center;border-bottom:.5px solid var(--border)}
.heatmap-table td:first-child{text-align:left;font-weight:500;color:var(--text);font-size:12px;max-width:160px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hm-cell{font-size:11px;font-weight:600;border-radius:4px;padding:4px 6px;display:inline-block;min-width:58px}

/* View selector tabs */
.view-tabs{display:flex;gap:4px;background:var(--bg-alt);border-radius:6px;padding:3px}
.view-tab{font-family:'DM Sans',sans-serif;font-size:11px;font-weight:500;padding:4px 10px;border-radius:4px;border:none;background:transparent;color:var(--muted);cursor:pointer;transition:all .15s}
.view-tab.active{background:var(--surface);color:var(--text);box-shadow:0 1px 4px rgba(0,0,0,.08)}

/* DISPLAY MODE / ACTIONS */
.toolbar{display:flex;align-items:center;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.toolbar-label{font-size:11px;color:var(--hint);font-weight:500}
.mode-select{font-family:'DM Sans',sans-serif;font-size:12px;padding:5px 8px;border-radius:4px;border:.5px solid var(--border-strong);background:var(--surface);color:var(--text)}
.spacer{flex:1}
.missing-report{margin-top:10px;font-size:11px;color:var(--muted);line-height:1.7}
</style>
</head>
<body>
<nav class="nav">
  <span class="nav-logo">MiSt MealCalc</span>
  <span class="nav-tag">RIVM data</span>
</nav>

<div class="page">

  <!-- LEFT: search + meal builder -->
  <div>
    <!-- Search panel -->
    <div class="panel" style="margin-bottom:16px">
      <div class="panel-title">Add ingredient</div>
      <div class="search-row">
        <input class="search-input" id="q" type="text" placeholder="e.g. chicken, lentils, potato…" onkeydown="if(event.key==='Enter')search()">
        <button class="btn btn-primary" onclick="search()">Search</button>
      </div>
      <div class="section-label">Matches — click to select &amp; add</div>
      <div class="match-grid" id="results"><div style="font-size:12px;color:var(--hint);grid-column:1/-1">Type an ingredient and press Search.</div></div>
    </div>

    <!-- Meal builder panel -->
    <div class="panel">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
        <div class="panel-title" style="margin-bottom:0;flex-shrink:0">Meal</div>
        <input class="search-input" id="dishName" type="text" placeholder="Dish name (e.g. Chicken rice bowl)" style="flex:1;font-size:13px">
      </div>
      <div id="mealList"><div class="meal-empty">No ingredients yet.</div></div>

      <div class="chips" id="totalsRow">
        <div class="chip"><div class="chip-val" id="chip_co2_val">—</div><div class="chip-lbl" id="chip_co2_lbl">kg CO₂e</div></div>
        <div class="chip"><div class="chip-val" id="chip_water_val">—</div><div class="chip-lbl" id="chip_water_lbl">m³ water</div></div>
        <div class="chip"><div class="chip-val" id="chip_land_val">—</div><div class="chip-lbl" id="chip_land_lbl">m²a land</div></div>
      </div>

      <div class="toolbar">
        <span class="toolbar-label">Scale</span>
        <select class="mode-select" id="displayMode"><option value="total">Total meal</option><option value="100g">per 100 g</option></select>
        <div class="view-tabs" id="viewTabs">
          <button class="view-tab active" onclick="setView('A',this)">Bars</button>
          <button class="view-tab" onclick="setView('B',this)">Radar</button>
          <button class="view-tab" onclick="setView('C',this)">Heatmap</button>
        </div>
        <div class="spacer"></div>
        <button class="btn btn-ghost btn-sm" onclick="checkMissing()">Coverage</button>
        <button class="btn btn-ghost btn-sm" onclick="exportPNG()">Export PNG</button>
        <button class="btn btn-primary" onclick="calculateMeal()">Calculate</button>
      </div>

      <div id="mealResult"></div>
      <div id="missingReport" class="missing-report"></div>
    </div>
  </div>

  <!-- RIGHT: info / instructions -->
  <div>
    <div class="panel">
      <div class="panel-title">How it works</div>
      <p style="font-size:13px;color:var(--muted);line-height:1.7;margin-bottom:14px">Search for ingredients, select from the matched options, set amounts, then hit <strong style="color:var(--green-mid)">Calculate</strong> to see CO₂, water, and land footprints for your whole meal.</p>
      <div class="section-label">Data source</div>
      <p style="font-size:12px;color:var(--hint);line-height:1.6">RIVM — Rijksinstituut voor Volksgezondheid en Milieu (NL) environmental impact database for food products. 411 items with lifecycle footprint data.</p>
    </div>
  </div>

</div>

<script>
let meal = [];
let selectedName = null;

function parseName(full){
  const parts = full.split('|').map(s=>s.trim()).filter(Boolean);
  return { primary: parts[0], detail: parts.slice(1).join(' · ') };
}

async function search(){
  const q = document.getElementById('q').value.trim();
  if(!q) return;
  const el = document.getElementById('results');
  el.innerHTML = '<div style="font-size:12px;color:var(--hint);grid-column:1/-1">Searching…</div>';
  const res = await fetch('/ingredient?name=' + encodeURIComponent(q));
  if(!res.ok){ el.innerHTML = '<div style="font-size:12px;color:var(--red);grid-column:1/-1">No matches found.</div>'; return; }
  const data = await res.json();
  const out = data.matches || [];
  el.innerHTML = '';
  if(!out.length){ el.innerHTML = '<div style="font-size:12px;color:var(--hint);grid-column:1/-1">No matches.</div>'; return; }
  out.forEach(m => {
    const {primary, detail} = parseName(m.name);
    const card = document.createElement('button');
    card.className = 'match-card';
    card.innerHTML = `<div class="match-card-name">${primary}</div>${detail ? '<div class="match-card-detail">'+detail+'</div>' : ''}<span class="match-score">${m.score}% match</span>`;
    card.onclick = () => {
      document.querySelectorAll('.match-card').forEach(c=>c.classList.remove('selected'));
      card.classList.add('selected');
      selectedName = m.name;
      addToMeal(m.name);
    };
    el.appendChild(card);
  });
}

function syncMealFromDOM(){
  // persist any edited amounts/units back into meal[] before re-rendering
  meal.forEach((it, idx) => {
    const amtEl  = document.getElementById(`amt${idx}`);
    const unitEl = document.getElementById(`unit${idx}`);
    if(amtEl)  it.amount = parseFloat(amtEl.value)  || it.amount;
    if(unitEl) it.unit   = unitEl.value || it.unit;
  });
}

function addToMeal(name){
  syncMealFromDOM();
  const lname = name.toLowerCase();
  let amount = 100, unit = 'g';
  if(lname.includes('egg')){ amount=50; }
  if(lname.includes('carrot')){ amount=61; }
  if(lname.includes('onion')){ amount=110; }
  if(lname.includes('tomato')){ amount=123; }
  meal.push({name, amount, unit});
  renderMealList();
}

function renderMealList(){
  const el = document.getElementById('mealList');
  if(!meal.length){ el.innerHTML='<div class="meal-empty">No ingredients yet.</div>'; return; }
  el.innerHTML = '';
  meal.forEach((it, idx) => {
    const {primary, detail} = parseName(it.name);
    const row = document.createElement('div');
    row.className = 'meal-item';
    row.innerHTML = `
      <div class="meal-item-name">
        <div>${primary}</div>
        ${detail ? '<div class="meal-item-name-detail">'+detail+'</div>' : ''}
      </div>
      <div class="meal-item-controls">
        <input class="qty-input" id="amt${idx}" value="${it.amount}" type="number" min="0">
        <select class="unit-select" id="unit${idx}">
          <option>g</option><option>kg</option><option>ml</option><option>l</option><option>piece</option>
        </select>
        <button class="btn btn-danger" onclick="removeItem(${idx})">✕</button>
      </div>`;
    el.appendChild(row);
    document.getElementById(`unit${idx}`).value = it.unit;
  });
}

function removeItem(i){ syncMealFromDOM(); meal.splice(i,1); renderMealList(); }

let currentView = 'A';
let lastResultData = null;

function setView(v, btn){
  currentView = v;
  document.querySelectorAll('.view-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  if(lastResultData) renderResults(lastResultData);
}

function altHtmlFor(d){
  if(!d.alternative) return '';
  const altPrimary = parseName(d.alternative.name || '').primary;
  return `<div class="alt-row">
    <span>Lower impact: <span class="alt-name">${altPrimary}</span> (−${d.alternative.delta.toFixed(2)} kgCO₂/kg)</span>
    <button class="btn btn-ghost btn-sm" onclick="swapItem('${d.requested.replace(/'/g,"\\'")}','${(d.alternative.name||'').replace(/'/g,"\\'")}')">Swap</button>
  </div>`;
}

function renderResults({details, scale, suffix, totalCo2, totalWater, totalLand}){
  const el = document.getElementById('mealResult');
  el.innerHTML = '';
  if(!details.length) return;

  // pre-compute per-item display values
  const items = details.map(d => {
    const co2   = (d.contrib || 0) * scale;
    const water = (d.perkg_water != null && d.kg) ? d.perkg_water * d.kg * scale : null;
    const land  = (d.perkg_land  != null && d.kg) ? d.perkg_land  * d.kg * scale : null;
    return { d, primary: parseName(d.matched||d.requested).primary, co2, water, land };
  });

  // per-metric max for normalisation
  const maxCo2   = Math.max(1e-9, ...items.map(i=>i.co2));
  const maxWater = Math.max(1e-9, ...items.map(i=>i.water??0));
  const maxLand  = Math.max(1e-9, ...items.map(i=>i.land??0));

  if(currentView === 'A') renderViewA(el, items, maxCo2, maxWater, maxLand, suffix);
  else if(currentView === 'B') renderViewB(el, items, maxCo2, maxWater, maxLand, suffix);
  else renderViewC(el, items, maxCo2, maxWater, maxLand, suffix);
}

/* ---- Option A: stacked proportion bars (name | bar | total) ---- */
function renderViewA(el, items, maxCo2, maxWater, maxLand, suffix){
  // header + legend
  const hdr = document.createElement('div');
  hdr.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px">
      <span style="font-size:13px;font-weight:600;color:var(--green-deep)">Impact breakdown per ingredient</span>
      <div style="display:flex;gap:12px">
        <span style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--hint)"><span style="width:8px;height:8px;border-radius:50%;background:#E24B4A;display:inline-block"></span>CO₂</span>
        <span style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--hint)"><span style="width:8px;height:8px;border-radius:50%;background:#378ADD;display:inline-block"></span>Water</span>
        <span style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--hint)"><span style="width:8px;height:8px;border-radius:50%;background:#52B788;display:inline-block"></span>Land</span>
      </div>
    </div>`;
  el.appendChild(hdr);

  items.forEach(({d, primary, co2, water, land}) => {
    // proportional segments: normalise each metric to its own max, then split bar
    const rCo2   = co2 / (maxCo2 || 1);
    const rWater = (water ?? 0) / (maxWater || 1);
    const rLand  = (land  ?? 0) / (maxLand  || 1);
    const tot    = rCo2 + rWater + rLand || 1;
    const pCo2   = (rCo2  /tot*100).toFixed(1);
    const pWater = (rWater/tot*100).toFixed(1);
    const pLand  = (rLand /tot*100).toFixed(1);

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:0.5px solid var(--border)';
    row.innerHTML = `
      <div style="font-size:13px;font-weight:500;color:var(--text);width:130px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${primary}">${primary}</div>
      <div style="flex:1;height:18px;border-radius:4px;overflow:hidden;display:flex;background:#EDEBE3">
        <div style="width:${pCo2}%;background:#E24B4A;opacity:.9"></div>
        <div style="width:${pWater}%;background:#378ADD;opacity:.9"></div>
        <div style="width:${pLand}%;background:#52B788;opacity:.9"></div>
      </div>
      <div style="font-size:12px;color:var(--muted);width:72px;text-align:right;flex-shrink:0;white-space:nowrap">${co2.toFixed(3)} kg</div>`;
    el.appendChild(row);

    // alt suggestion inline
    if(d.alternative){
      const altPrimary = parseName(d.alternative.name||'').primary;
      const alt = document.createElement('div');
      alt.className = 'alt-row';
      alt.style.marginLeft = '140px';
      alt.innerHTML = `<span>Lower impact: <span class="alt-name">${altPrimary}</span> (−${d.alternative.delta.toFixed(2)} kgCO₂/kg)</span>
        <button class="btn btn-ghost btn-sm" onclick="swapItem('${d.requested.replace(/'/g,"\\'")}','${(d.alternative.name||'').replace(/'/g,"\\'")}')">Swap</button>`;
      el.appendChild(alt);
    }
  });
}

/* ---- Option B: SVG radar — one overlay, all ingredients ---- */
function renderViewB(el, items, maxCo2, maxWater, maxLand, suffix){
  const ingColors = ['#2D6A4F','#378ADD','#D4A017','#E24B4A','#9B5DE5','#F15BB5'];
  const cx=110, cy=110, r=80;
  const axes = ['CO₂','Water','Land'];
  const N=3;
  const angle = i => (i * 2*Math.PI/N) - Math.PI/2;

  let svgStr = '';
  // grid rings
  [0.25,0.5,0.75,1].forEach(f=>{
    const pts = Array.from({length:N},(_,i)=>`${cx+r*f*Math.cos(angle(i))},${cy+r*f*Math.sin(angle(i))}`).join(' ');
    svgStr += `<polygon points="${pts}" fill="none" stroke="rgba(26,58,42,0.1)" stroke-width="0.5"/>`;
  });
  // spokes + axis labels
  axes.forEach((ax,i)=>{
    const x=cx+r*Math.cos(angle(i)), y=cy+r*Math.sin(angle(i));
    svgStr += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="rgba(26,58,42,0.12)" stroke-width="0.5"/>`;
    const lx=cx+(r+18)*Math.cos(angle(i)), ly=cy+(r+18)*Math.sin(angle(i));
    svgStr += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#5A5A50" font-family="DM Sans,sans-serif" font-weight="600">${ax}</text>`;
  });
  // one polygon per ingredient
  items.forEach(({primary, co2, water, land}, ii) => {
    const color = ingColors[ii % ingColors.length];
    const vals = [co2/(maxCo2||1), (water??0)/(maxWater||1), (land??0)/(maxLand||1)];
    const pts = vals.map((v,i)=>`${cx+r*Math.max(0.03,v)*Math.cos(angle(i))},${cy+r*Math.max(0.03,v)*Math.sin(angle(i))}`).join(' ');
    svgStr += `<polygon points="${pts}" fill="${color}" fill-opacity="0.12" stroke="${color}" stroke-width="1.5"/>`;
    vals.forEach((v,i)=>{
      svgStr += `<circle cx="${cx+r*Math.max(0.03,v)*Math.cos(angle(i))}" cy="${cy+r*Math.max(0.03,v)*Math.sin(angle(i))}" r="3.5" fill="${color}"/>`;
    });
  });

  // legend
  const legendItems = items.map(({d, primary, co2, water, land}, ii) => {
    const color = ingColors[ii % ingColors.length];
    const altH = altHtmlFor(d);
    return `<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px">
      <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0;margin-top:3px"></div>
      <div>
        <div style="font-size:12px;font-weight:500;color:var(--text)">${primary}</div>
        <div style="font-size:11px;color:var(--hint)">CO₂ ${co2.toFixed(3)} · Water ${water!=null?water.toFixed(3):'n/a'} · Land ${land!=null?land.toFixed(3):'n/a'}</div>
        ${altH}
      </div>
    </div>`;
  }).join('');

  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap';
  wrap.innerHTML = `
    <svg width="220" height="220" viewBox="0 0 220 220" style="flex-shrink:0">${svgStr}</svg>
    <div style="padding-top:8px;flex:1;min-width:140px">${legendItems}</div>`;
  el.appendChild(wrap);
}

/* ---- Option C: heatmap tile grid ---- */
function renderViewC(el, items, maxCo2, maxWater, maxLand, suffix){
  const palettes = {
    co2:   ['#FCEAE9','#F09595','#E24B4A','#A32D2D'],
    water: ['#E6F1FB','#85B7EB','#378ADD','#185FA5'],
    land:  ['#D8F3DC','#B7E4C7','#52B788','#2D6A4F'],
  };
  const textOn = {
    co2:   ['#A32D2D','#791F1F','#fff','#fff'],
    water: ['#185FA5','#0C447C','#fff','#fff'],
    land:  ['#2D6A4F','#1A3A2A','#fff','#fff'],
  };
  const maxes = {co2: maxCo2, water: maxWater, land: maxLand};

  function tileHtml(val, metric, unit){
    if(val == null) return `<div style="background:#F3F3F0;border-radius:6px;padding:10px 8px;text-align:center"><span style="font-size:13px;color:#ccc">n/a</span></div>`;
    const allVals = items.map(it => it[metric] ?? 0);
    const mn=Math.min(...allVals), mx=Math.max(...allVals);
    const lv = Math.min(3, Math.floor((val-mn)/((mx-mn)||1)*4));
    const bg=palettes[metric][lv], fg=textOn[metric][lv];
    return `<div style="background:${bg};border-radius:6px;padding:10px 8px;text-align:center">
      <div style="font-size:15px;font-weight:600;color:${fg};line-height:1">${val.toFixed(3)}</div>
      <div style="font-size:9px;color:${fg};opacity:.7;margin-top:2px;text-transform:uppercase;letter-spacing:.06em">${unit}</div>
    </div>`;
  }

  const rows = items.map(({d, primary, co2, water, land}) => `
    <div style="display:contents">
      <div style="font-size:12px;font-weight:500;color:var(--text);display:flex;align-items:center;padding:4px 0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${primary}">${primary}</div>
      ${tileHtml(co2,   'co2',   'kg CO₂')}
      ${tileHtml(water, 'water', 'm³')}
      ${tileHtml(land,  'land',  'm²a')}
    </div>`).join('');

  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:grid;grid-template-columns:130px repeat(3,1fr);gap:6px;align-items:center';
  wrap.innerHTML = `
    <div></div>
    <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#E24B4A;text-align:center;padding-bottom:4px">CO₂${suffix}</div>
    <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#378ADD;text-align:center;padding-bottom:4px">Water${suffix}</div>
    <div style="font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#52B788;text-align:center;padding-bottom:4px">Land${suffix}</div>
    ${rows}`;
  el.appendChild(wrap);

  // alt suggestions below grid
  items.forEach(({d}) => {
    const a = altHtmlFor(d);
    if(a){ const div=document.createElement('div'); div.innerHTML=a; el.appendChild(div); }
  });
}

async function calculateMeal(){
  if(!meal.length) return;
  const items = meal.map((it,idx)=>({
    name: it.name,
    amount: parseFloat(document.getElementById(`amt${idx}`).value || it.amount),
    unit: document.getElementById(`unit${idx}`).value || it.unit
  }));
  const res = await fetch('/meal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items})});
  const data = await res.json();
  const details = data.details || [];
  const mode = document.getElementById('displayMode').value;

  let totalCo2 = data.total_co2_kgCO2eq || 0;
  let totalWater = 0, totalLand = 0, totalKg = 0;
  details.forEach(d => {
    if(d.perkg_water != null && d.kg) totalWater += d.perkg_water * d.kg;
    if(d.perkg_land  != null && d.kg) totalLand  += d.perkg_land  * d.kg;
    if(d.kg) totalKg += d.kg;
  });

  const totalG = totalKg * 1000;
  const scale = (mode === '100g' && totalG > 0) ? (100 / totalG) : 1;
  const suffix = mode === '100g' ? '/100g' : '';

  document.getElementById('chip_co2_val').textContent  = (totalCo2   * scale).toFixed(3);
  document.getElementById('chip_water_val').textContent = (totalWater * scale).toFixed(3);
  document.getElementById('chip_land_val').textContent  = (totalLand  * scale).toFixed(3);
  document.getElementById('chip_co2_lbl').textContent   = 'kg CO₂e' + suffix;
  document.getElementById('chip_water_lbl').textContent = 'm³ water' + suffix;
  document.getElementById('chip_land_lbl').textContent  = 'm²a land' + suffix;

  lastResultData = {details, scale, suffix, totalCo2, totalWater, totalLand};
  renderResults(lastResultData);
}

async function checkMissing(){
  const items = meal.map(it=>({name:it.name}));
  const res = await fetch('/missing',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items})});
  if(!res.ok){ document.getElementById('missingReport').textContent='Check failed'; return; }
  const json = await res.json();
  const el = document.getElementById('missingReport');
  if(json.missing&&json.missing.length){
    el.innerHTML='<strong>Missing footprints:</strong><br>'+json.missing.map(m=>m.requested+(m.matched?' → '+m.matched:'')).join('<br>');
  } else {
    el.innerHTML='<strong style="color:var(--green-mid)">All ingredients have RIVM footprint data.</strong>';
  }
}

function swapItem(requested, altName){
  for(let i=0;i<meal.length;i++){ if(meal[i].name===requested){meal[i].name=altName;break;} }
  renderMealList();
}

function exportPNG(){
  if(!lastResultData){ alert('Calculate the meal first.'); return; }
  const dishName = document.getElementById('dishName').value.trim() || 'Meal Report';
  const {details, scale, suffix, totalCo2, totalWater, totalLand} = lastResultData;

  // ── pre-compute items ────────────────────────────────
  const ritems = details.map(d => {
    const co2   = (d.contrib||0)*scale;
    const water = (d.perkg_water!=null&&d.kg) ? d.perkg_water*d.kg*scale : 0;
    const land  = (d.perkg_land !=null&&d.kg) ? d.perkg_land *d.kg*scale : 0;
    const grams = Math.round((d.kg||0)*1000);
    const amtStr = grams>=1000 ? (grams/1000).toFixed(2)+' kg' : grams+' g';
    return { name: parseName(d.matched||d.requested).primary, co2, water, land, amount: amtStr };
  });

  // ── design tokens (matching HTML template exactly) ──
  const BG='#F5F2EA', SURFACE='#FFFFFF', GREEN_DEEP='#1A3A2A', GREEN_MID='#2D6A4F';
  const GREEN_LIGHT='#B7E4C7', GREEN_PALE='#D8F3DC';
  const HINT='#9A9A8A', MUTED='#5A5A50', TEXT='#1A1A18';
  const CO2_C='#D94F3D', WATER_C='#3A7BBF', LAND_C='#52B788';
  const BORDER_C='rgba(26,58,42,0.13)';
  const SAN="DM Sans,Arial,sans-serif", SER="Georgia,'DM Serif Display',serif";

  // ── layout constants ─────────────────────────────────
  // HTML: body padding 40, report max-width 860 → inner W = 860
  const W=860, PAD=40;
  const GAP=14, R=14, CP=22;    // card-padding=22 matches HTML padding:20px 22px

  // section heights derived from HTML measurements
  const H_HDR  = 110;  // header: 28+22+24 padding + brand(22)+sub(15)+dish(28) ≈ 110
  const H_CARD = 92;   // total-card: 16+18 padding + label(10)+gap(8)+value(28)+gap(4)+unit(11) = 95
  const H_EQV  = 30;   // equiv badges pill row
  const H_BRKH = 44;   // breakdown card header row (col labels + separator)
  const ROW_H  = 52;   // ing-row: 12+12 padding + name(14)+amount(11) ≈ 52 (matches padding:12px 0 + content)
  const H_FTR  = 40;   // footer
  const totalH = PAD + H_HDR + GAP
               + H_CARD + GAP
               + H_EQV  + GAP
               + (H_BRKH + ritems.length*ROW_H + CP) + GAP
               + H_FTR  + PAD;

  const cv=document.createElement('canvas');
  cv.width=W*2; cv.height=totalH*2;
  const cx=cv.getContext('2d');
  cx.scale(2,2);

  // ── helpers ───────────────────────────────────────────
  function rr(x,y,w,h,rad,fill,stroke){
    cx.beginPath();
    cx.moveTo(x+rad,y);
    cx.arcTo(x+w,y,x+w,y+h,rad); cx.arcTo(x+w,y+h,x,y+h,rad);
    cx.arcTo(x,y+h,x,y,rad);     cx.arcTo(x,y,x+w,y,rad);
    cx.closePath();
    if(fill){cx.fillStyle=fill;cx.fill();}
    if(stroke){cx.strokeStyle=stroke;cx.lineWidth=0.5;cx.stroke();}
  }
  function t(s,x,y,font,color,align='left'){
    cx.font=font; cx.fillStyle=color; cx.textAlign=align; cx.fillText(String(s),x,y); cx.textAlign='left';
  }
  function hline(x1,x2,y,color='rgba(26,58,42,0.13)'){
    cx.strokeStyle=color; cx.lineWidth=0.5;
    cx.beginPath(); cx.moveTo(x1,y); cx.lineTo(x2,y); cx.stroke();
  }
  function dot(x,y,r2,color){ cx.beginPath(); cx.arc(x,y,r2,0,Math.PI*2); cx.fillStyle=color; cx.fill(); }

  // ── canvas background ─────────────────────────────────
  cx.fillStyle=BG; cx.fillRect(0,0,W,totalH);

  let y=PAD;

  // ════════════════════════════════════════════════════
  // HEADER  — green-deep rounded card
  // ════════════════════════════════════════════════════
  rr(PAD,y,W-PAD*2,H_HDR,R,GREEN_DEEP);
  // decorative circle (matches ::before pseudo-element)
  cx.save(); cx.globalAlpha=0.07;
  cx.beginPath(); cx.arc(W-PAD-40,y-30,160,0,Math.PI*2);
  cx.fillStyle='#52B788'; cx.fill(); cx.restore();

  // brand — left column
  t('MiSt MealCalc', PAD+28, y+34, `italic 600 22px ${SER}`,         '#fff');
  t('Meal Report',   PAD+28, y+54, `400 14px ${SAN}`,                 'rgba(255,255,255,0.65)');
  // dish name — prominent, green-light, matches an h2 style
  t(dishName,        PAD+28, y+90, `600 26px ${SAN}`,                 GREEN_LIGHT);

  // meta — right column (matches .header-meta)
  const dateStr=new Date().toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
  t('RIVM data', W-PAD-28, y+34, `500 12px ${SAN}`, 'rgba(255,255,255,0.45)', 'right');
  t(dateStr,     W-PAD-28, y+54, `400 12px ${SAN}`, 'rgba(255,255,255,0.35)', 'right');

  y += H_HDR + GAP;

  // ════════════════════════════════════════════════════
  // TOTALS GRID  — 3 white cards, colored accent stripe
  // ════════════════════════════════════════════════════
  const cW=(W-PAD*2-GAP*2)/3;
  [
    {lbl:'CO₂ EQUIVALENT', val:(totalCo2*scale).toFixed(3),   unit:'kg CO₂e'+suffix, color:CO2_C},
    {lbl:'WATER USE',       val:(totalWater*scale).toFixed(3), unit:'m³'+suffix,       color:WATER_C},
    {lbl:'LAND USE',        val:(totalLand*scale).toFixed(3),  unit:'m²a'+suffix,      color:LAND_C},
  ].forEach(({lbl,val,unit,color},i) => {
    const tx=PAD+i*(cW+GAP);
    // white card with border
    rr(tx,y,cW,H_CARD,R,SURFACE,BORDER_C);
    // 3px left accent stripe — draw as narrow rect clipped to card corners
    cx.save(); rr(tx,y,cW,H_CARD,R); cx.clip();
    cx.fillStyle=color; cx.fillRect(tx,y,3,H_CARD);
    cx.restore();
    // text — matching HTML: label(10px 600 caps), value(28px serif), unit(11px)
    // card has padding:16px 18px → baseline starts at ty+16
    const ti=tx+18;
    t(lbl,         ti, y+22,  `600 9px ${SAN}`,  HINT);       // label: 10px → 9px canvas
    t(val,         ti, y+62,  `600 28px ${SER}`,  GREEN_DEEP); // large serif number
    t(unit,        ti, y+78,  `400 11px ${SAN}`,  HINT);       // unit
  });

  y += H_CARD + GAP;

  // ════════════════════════════════════════════════════
  // EQUIVALENCY BADGES  — 3 pills
  // ════════════════════════════════════════════════════
  const badges=[
    {text:'≈ '+(totalCo2*scale/0.150).toFixed(1)+' km driven',          bg:'#FCEAE9', fg:'#8B2A2A'},
    {text:'≈ '+(totalWater*scale/0.065).toFixed(1)+' showers of water', bg:'#F4E4B0', fg:'#7A5C00'},
    {text:'≈ '+(totalCo2*scale/21).toFixed(2)+' trees/yr to offset',    bg:GREEN_PALE, fg:GREEN_MID},
  ];
  let bx=PAD;
  cx.font=`500 11px ${SAN}`;
  badges.forEach(b=>{
    const bw=cx.measureText(b.text).width+24, bh=26;
    rr(bx,y,bw,bh,13,b.bg);
    t(b.text, bx+12, y+17, `500 11px ${SAN}`, b.fg);
    bx+=bw+8;
  });

  y += H_EQV + GAP;

  // ════════════════════════════════════════════════════
  // INGREDIENT BREAKDOWN CARD
  // matching HTML: grid-template-columns: 160px 1fr 72px; gap:12px
  // ════════════════════════════════════════════════════
  const bcardH = H_BRKH + ritems.length*ROW_H + CP;
  rr(PAD,y,W-PAD*2,bcardH,R,SURFACE,BORDER_C);

  // column geometry — matches HTML grid exactly
  const IC  = PAD+CP;                      // inner card x-start
  const IW  = W-PAD*2-CP*2;               // inner card width
  const NW  = 160;                         // name column
  const VW  = 72;                          // CO2 value column
  const G12 = 12;                          // grid gap
  const BX  = IC+NW+G12;                  // bar x-start
  const BW  = IW-NW-G12-G12-VW;          // bar width
  const VX  = BX+BW+G12;                  // value x-start

  // breakdown card header row
  let hy=y+CP;
  t('INGREDIENT', IC, hy+12, `600 9px ${SAN}`, HINT);
  // legend dots + labels (inline, left of bar area)
  [[CO2_C,'CO₂'],[WATER_C,'Water'],[LAND_C,'Land']].forEach(([col,lbl],i)=>{
    const lx=BX+i*60;
    dot(lx+4, hy+8, 4, col);
    t(lbl, lx+12, hy+12, `500 10px ${SAN}`, HINT);
  });
  // "proportion" label
  t('PROPORTION', BX+190, hy+12, `600 9px ${SAN}`, HINT);
  t('CO₂ (kg)', VX+VW, hy+12, `600 9px ${SAN}`, HINT, 'right');

  hy += 20;
  hline(IC, W-PAD-CP, hy, BORDER_C);
  hy += 4;

  // ingredient rows — matches .ing-row padding:12px 0
  ritems.forEach((item,i)=>{
    const ry=hy+i*ROW_H;

    // name (14px 500) + amount (11px hint) — matches .ing-name / .ing-amount
    const nm=item.name.length>22 ? item.name.slice(0,21)+'…' : item.name;
    t(nm,          IC, ry+20, `500 13px ${SAN}`, TEXT);
    t(item.amount, IC, ry+35, `400 10px ${SAN}`, HINT);

    // stacked bar — matches .stacked-bar height:20px, background:#F0EDE6
    const BAR_H=20, barY=ry+(ROW_H-BAR_H)/2;
    rr(BX,barY,BW,BAR_H,4,'#F0EDE6');
    const tot=item.co2+item.water+item.land||1;
    let sx=BX;
    [[item.co2/tot,CO2_C],[item.water/tot,WATER_C],[item.land/tot,LAND_C]].forEach(([f,col])=>{
      const sw=Math.max(0,f*BW); if(sw<1) return;
      cx.save(); rr(BX,barY,BW,BAR_H,4); cx.clip();
      cx.fillStyle=col; cx.globalAlpha=0.82; cx.fillRect(sx,barY,sw,BAR_H);
      cx.globalAlpha=1; cx.restore(); sx+=sw;
    });

    // CO2 value (14px 600 co2-color, right-aligned) — matches .ing-co2-val
    t(item.co2.toFixed(3), VX+VW, ry+26, `600 14px ${SAN}`, CO2_C, 'right');

    // row separator (skip last)
    if(i<ritems.length-1) hline(IC, W-PAD-CP, ry+ROW_H, BORDER_C);
  });

  y += bcardH + GAP;

  // ════════════════════════════════════════════════════
  // FOOTER  — matches .footer (border-top, flex space-between)
  // ════════════════════════════════════════════════════
  hline(PAD, W-PAD, y+8, BORDER_C);
  t('Generated by MiSt MealCalc · RIVM environmental impact database · mist-mealcalc',
    PAD, y+26, `400 10px ${SAN}`, HINT);
  t('MiSt', W-PAD, y+26, `italic 600 13px ${SER}`, HINT, 'right');

  // ── download ─────────────────────────────────────────
  const slug=dishName.replace(/[^a-z0-9]+/gi,'-').toLowerCase()||'meal';
  const a=document.createElement('a');
  a.href=cv.toDataURL('image/png');
  a.download=slug+'-impact.png';
  document.body.appendChild(a); a.click(); a.remove();
}
</script>
</body>
</html>"""
    return Response(content=html, media_type='text/html')

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=9000)

