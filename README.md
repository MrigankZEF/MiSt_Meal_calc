MiSt MealCalc — local run instructions

Requirements
- Python 3.10+
- (recommended) create and activate the provided virtualenv: `.venv`
- packages: fastapi, uvicorn, pandas, rapidfuzz

Quick run (from project root `projects/mist-mealcalc`):

1) Activate venv:
   source .venv/bin/activate
2) Install deps (if not already installed):
   pip install fastapi uvicorn pandas rapidfuzz
3) Start server:
   .venv/bin/uvicorn app:app --host 127.0.0.1 --port 9000
4) Open http://127.0.0.1:9000 in a browser

Notes
- The app reads footprints from `rivm.db` (already present). Do not replace this DB unless you mean to update the RIVM dataset.
- Local piece weights and synonyms are stored in `data/ingredients.csv` and are used only for unit heuristics (not for per-kg footprints).
- To export a meal, the demo UI calls `/export` which returns a CSV summary.
