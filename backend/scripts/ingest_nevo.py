"""Ingest the NEVO2025 nutrition spreadsheet into `data/reference.db`.

Reads the `NEVO2025` sheet (2328 foods × 148 cols, per-100 g values) and
writes the `nevo_nutrition` table *into the same reference DB as RIVM*
(VISION §4.1: "one SQLite for all committed reference data"). Each row
carries a curated set of macro/micro columns plus a lossless JSON dump of
all 148 original columns in `raw_nutrients`.

Run:
    cd backend
    python scripts/ingest_nevo.py

Re-runs are safe: drops + recreates `nevo_nutrition` only. Does NOT touch
`rivm_item`. Assumes `ingest_rivm.py` has already been run.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Make `app.*` importable when running as a loose script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.config import DATA_DIR, DEFAULT_REFERENCE_DB
from app.db.base import Base
from app.models.reference import NevoNutrition, RivmItem

SOURCE_DIR = DATA_DIR / "source"
SOURCE_GLOB = "NEVO2025*.xlsx"
SHEET_NAME = "NEVO2025"

# XLSX col → ORM attribute. Anything not listed still lands in raw_nutrients.
CURATED_COLUMNS: dict[str, str] = {
    "ENERCJ (kJ)": "kj",
    "ENERCC (kcal)": "kcal",
    "WATER (g)": "water_g",
    "PROT (g)": "protein_g",
    "PROTPL (g)": "protein_plant_g",
    "PROTAN (g)": "protein_animal_g",
    "FAT (g)": "fat_g",
    "FASAT (g)": "fat_saturated_g",
    "FAMSCIS (g)": "fat_mono_g",
    "FAPU (g)": "fat_poly_g",
    "CHO (g)": "carb_g",
    "SUGAR (g)": "sugar_g",
    "STARCH (g)": "starch_g",
    "FIBT (g)": "fibre_g",
    "ALC (g)": "alcohol_g",
    "NA (mg)": "sodium_mg",
    "CA (mg)": "calcium_mg",
    "FE (mg)": "iron_mg",
    "VITC (mg)": "vitamin_c_mg",
    "VITD (µg)": "vitamin_d_ug",
}


def find_source() -> Path:
    matches = sorted(SOURCE_DIR.glob(SOURCE_GLOB))
    # Filter out Zone.Identifier sidecar files from Windows.
    matches = [m for m in matches if m.suffix.lower() == ".xlsx"]
    if not matches:
        raise SystemExit(
            f"No NEVO source xlsx found under {SOURCE_DIR} (looking for {SOURCE_GLOB!r})."
        )
    return matches[-1]


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def _str_or_none(v: object) -> str | None:
    if v is None:
        return None
    try:
        if pd.isna(v):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s or None


def _int_or_none(v: object) -> int | None:
    f = _float_or_none(v)
    return int(f) if f is not None else None


def _row_to_raw(row: pd.Series) -> dict[str, object]:
    """Full 148-col row as a JSON-safe dict. Floats preserved, NaN → None,
    everything else stringified."""
    out: dict[str, object] = {}
    for col, val in row.items():
        key = str(col)
        try:
            if pd.isna(val):
                out[key] = None
                continue
        except (TypeError, ValueError):
            pass
        if isinstance(val, int | float):
            try:
                f = float(val)
                out[key] = None if math.isnan(f) or math.isinf(f) else f
            except (TypeError, ValueError):
                out[key] = None
        else:
            out[key] = str(val)
    return out


def ingest() -> None:
    source = find_source()
    target = DEFAULT_REFERENCE_DB

    if not target.exists():
        raise SystemExit(
            f"reference.db not found at {target}. Run scripts/ingest_rivm.py first."
        )

    print(f"source: {source.name}")
    print(f"target: {target} (nevo_nutrition only — rivm_item untouched)")
    print()

    engine = create_engine(f"sqlite:///{target.as_posix()}", future=True)
    Base.metadata.create_all(engine)  # idempotent; creates table if missing

    df = pd.read_excel(source, sheet_name=SHEET_NAME, header=0)
    df = df[df["NEVO-code"].notna()].copy()

    # Report which curated cols are actually present.
    missing = [c for c in CURATED_COLUMNS if c not in df.columns]
    if missing:
        print(f"note: curated columns not in xlsx (will be NULL): {missing}")

    total = 0
    skipped = 0
    with Session(engine) as session:
        # Clear any previous run; rivm_item untouched.
        session.execute(delete(NevoNutrition))
        session.commit()

        for _, row in df.iterrows():
            nevo_code = _int_or_none(row["NEVO-code"])
            if nevo_code is None:
                skipped += 1
                continue

            kwargs: dict[str, object] = {
                "nevo_code": nevo_code,
                "dutch_name": _str_or_none(row.get("Voedingsmiddelnaam/Dutch food name")),
                "english_name": _str_or_none(row.get("Engelse naam/Food name")),
                "synonym": _str_or_none(row.get("Synoniem")),
                "food_group_nl": _str_or_none(row.get("Voedingsmiddelgroep")),
                "food_group_en": _str_or_none(row.get("Food group")),
                "quantity": _str_or_none(row.get("Hoeveelheid/Quantity")),
                "raw_nutrients": _row_to_raw(row),
            }
            for xlsx_col, orm_attr in CURATED_COLUMNS.items():
                kwargs[orm_attr] = _float_or_none(row.get(xlsx_col))

            session.add(NevoNutrition(**kwargs))
            total += 1

        session.commit()

    print(f"Inserted {total} rows into nevo_nutrition (skipped {skipped} without NEVO code).")

    # Verification
    print()
    print("Verification:")
    with Session(engine) as session:
        n_rows = session.scalar(select(func.count()).select_from(NevoNutrition))
        n_kcal = session.scalar(
            select(func.count())
            .select_from(NevoNutrition)
            .where(NevoNutrition.kcal.is_not(None))
        )
        n_protein = session.scalar(
            select(func.count())
            .select_from(NevoNutrition)
            .where(NevoNutrition.protein_g.is_not(None))
        )
        # How many distinct RIVM NEVO codes can now be joined to nutrition?
        n_rivm_distinct = session.scalar(
            select(func.count(func.distinct(RivmItem.nevo_code))).where(
                RivmItem.nevo_code.is_not(None)
            )
        )
        n_joinable = session.scalar(
            select(func.count(func.distinct(RivmItem.nevo_code))).where(
                RivmItem.nevo_code.in_(select(NevoNutrition.nevo_code))
            )
        )

    print(f"  rows                 = {n_rows}")
    print(f"  with_kcal            = {n_kcal}")
    print(f"  with_protein         = {n_protein}")
    print(f"  rivm_nevo_distinct   = {n_rivm_distinct}")
    print(f"  rivm_codes_joinable  = {n_joinable}")
    if n_rivm_distinct:
        pct = 100.0 * (n_joinable or 0) / n_rivm_distinct
        print(f"  → {pct:.1f}% of RIVM NEVO codes have nutrition data")


if __name__ == "__main__":
    ingest()
