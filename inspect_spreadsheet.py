#!/usr/bin/env python3
import pandas as pd
from pathlib import Path
import json

XPATH = Path('/home/mriga/.openclaw/media/inbound/Database_milieubelasting_voedingsmiddelen_database_versie_23---75699552-61ae-46f6-b2d6-e695c8a5d9ae.xlsx')
if not XPATH.exists():
    print('Spreadsheet not found:', XPATH)
    raise SystemExit(1)

xls = pd.ExcelFile(XPATH)
info = {'sheets':{}}
for sheet in xls.sheet_names:
    try:
        df = pd.read_excel(xls, sheet_name=sheet)
        columns = list(df.columns)
        nrows = len(df)
        sample = df.head(3).fillna('').to_dict(orient='records')
        info['sheets'][sheet] = {'rows': nrows, 'columns': columns, 'sample': sample}
    except Exception as e:
        info['sheets'][sheet] = {'error': str(e)}

print(json.dumps(info, indent=2, ensure_ascii=False))
