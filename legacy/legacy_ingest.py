#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

XPATH = Path('/home/mriga/.openclaw/media/inbound/Database_milieubelasting_voedingsmiddelen_database_versie_23---75699552-61ae-46f6-b2d6-e695c8a5d9ae.xlsx')
OUTDB = Path('rivm.db')
SHEET='tot-en-met-consumptie'

print('reading', XPATH, 'sheet', SHEET)
# Read without inferring a single header so we can detect the header rows
# The sheet uses the third row (index 2) as the real column headers; load with header=2
df = pd.read_excel(XPATH, sheet_name=SHEET, header=2)

# Normalize column keys to friendly machine names where possible
rename = {}
for c in df.columns:
    lc = c.lower()
    if 'global warming' in lc or 'kg co2' in lc or 'co2' in lc:
        rename[c] = 'co2_kgco2eq'
    elif 'terrestrial' in lc or 'so2' in lc:
        rename[c] = 'so2_kg'
    elif 'land use' in lc or 'm2a' in lc:
        rename[c] = 'land_m2a'
    elif 'freshwater' in lc or 'kg p eq' in lc:
        rename[c] = 'p_kg'
    elif 'marine' in lc or 'kg n eq' in lc:
        rename[c] = 'n_kg'
    elif 'water' in lc or 'm3' in lc:
        rename[c] = 'water_m3'
    elif 'nevo' in lc or 'codering' in lc or 'code' in lc:
        rename[c] = 'nevo_code'
    elif 'naam' in lc or 'name' in lc:
        rename[c] = 'name'

if rename:
    df = df.rename(columns=rename)

# Keep the most relevant columns (name + metrics)
keep_cols = [c for c in ['name','nevo_code','co2_kgco2eq','so2_kg','p_kg','n_kg','land_m2a','water_m3'] if c in df.columns]
if not keep_cols:
    # fallback: keep all
    keep_cols = df.columns.tolist()
ndf = df[keep_cols].copy()
# ensure unique column names
ndf = ndf.loc[:, ~ndf.columns.duplicated()]
# Write to sqlite
engine = create_engine(f'sqlite:///{OUTDB}')
ndf.to_sql('consumption', engine, if_exists='replace', index=False)
print('wrote', OUTDB)
