from pathlib import Path
import pandas as pd

DATA_CSV = Path(__file__).resolve().parents[1] / 'data' / 'ingredients.csv'

def load_local_catalog():
    if not DATA_CSV.exists():
        return pd.DataFrame()
    df = pd.read_csv(DATA_CSV)
    # normalize column names to match expectations
    df = df.rename(columns={
        'perkg_co2':'co2', 'perkg_water':'water', 'perkg_land':'land', 'piece_g':'piece_g'
    })
    # ensure columns exist
    for c in ['name','co2','water','land','piece_g']:
        if c not in df.columns:
            df[c] = None
    return df

if __name__=='__main__':
    d = load_local_catalog()
    print('Loaded', len(d), 'local ingredients')
