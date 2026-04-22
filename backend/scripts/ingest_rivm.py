"""Ingest the RIVM environmental-impact spreadsheet into `data/reference.db`.

Reads all three stage sheets (distribution, retail, consumption) from
`data/source/Database milieubelasting voedingsmiddelen - ...xlsx` and writes
a single unified `rivm_item` table.

Run:
    cd backend
    python scripts/ingest_rivm.py

Re-runs are safe: the script drops and recreates `reference.db`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `app.*` importable when running as a loose script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.config import DATA_DIR, DEFAULT_REFERENCE_DB
from app.db.base import Base
from app.models.reference import RivmItem

SOURCE_DIR = DATA_DIR / "source"
SOURCE_GLOB = "Database milieubelasting*.xlsx"

STAGE_SHEETS: dict[str, str] = {
    "distribution": "tot-en-met-distributie",
    "retail": "tot-en-met-retail",
    "consumption": "tot-en-met-consumptie",
}

COL_RENAME: dict[str, str] = {
    "Naam": "raw_name",
    "kg CO2 eq": "co2_kgco2eq",
    "kg SO2 eq": "so2_kg",
    "kg P eq": "p_kg",
    "kg N eq": "n_kg",
    "m2a crop eq": "land_m2a",
    "m3": "water_m3",
    "NEVO code": "nevo_code",
    "NEVO naam": "nevo_naam_nl",
    "NEVO productgroep": "nevo_productgroup_nl",
    "NEVO name": "nevo_name_en",
    "NEVO productgroup": "nevo_productgroup_en",
}


def find_source() -> Path:
    matches = sorted(SOURCE_DIR.glob(SOURCE_GLOB))
    if not matches:
        raise SystemExit(
            f"No RIVM source xlsx found under {SOURCE_DIR} (looking for '{SOURCE_GLOB}')."
        )
    # Prefer the newest file if multiple are present.
    return matches[-1]


def parse_name(raw: str, stage: str) -> dict[str, str | None]:
    """Split pipe-delimited RIVM name into (primary, conditions, packaging, prep_method).

    Grammar per stage:
        distribution/retail: `<primary> | <conditions> | <packaging> | <stage suffix>`
        consumption:         `<primary> | <conditions> | <packaging> | <prep method> | <stage suffix>`
    """
    if not isinstance(raw, str):
        return {"primary_name": "", "conditions": None, "packaging": None, "prep_method": None}

    parts = [p.strip() for p in raw.split("|") if p.strip()]
    # Drop the trailing stage suffix (e.g. "at distribution/NL Economic", "consumed/NL Economic").
    if len(parts) >= 2:
        parts = parts[:-1]

    primary = parts[0] if parts else ""
    conditions = parts[1] if len(parts) >= 2 else None
    packaging = parts[2] if len(parts) >= 3 else None
    prep_method: str | None

    if stage == "retail":
        # Retail rows don't carry a prep-method segment; we label all of them "supermarket"
        # so the UI can group them under a single variant.
        prep_method = "supermarket"
    elif stage == "consumption":
        prep_method = parts[3].strip().lower() if len(parts) >= 4 else None
    else:  # distribution
        prep_method = None

    return {
        "primary_name": primary,
        "conditions": conditions,
        "packaging": packaging,
        "prep_method": prep_method,
    }


def _str_or_none(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    return s or None


def _float_or_none(v: object) -> float | None:
    if v is None:
        return None
    try:
        if pd.isna(v):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int_or_none(v: object) -> int | None:
    f = _float_or_none(v)
    return int(f) if f is not None else None


def ingest() -> None:
    source = find_source()
    target = DEFAULT_REFERENCE_DB
    target.parent.mkdir(parents=True, exist_ok=True)

    print(f"source: {source.name}")
    print(f"target: {target}")
    print()

    if target.exists():
        target.unlink()

    engine = create_engine(f"sqlite:///{target.as_posix()}", future=True)
    Base.metadata.create_all(engine)

    total = 0
    with Session(engine) as session:
        for stage, sheet_name in STAGE_SHEETS.items():
            df = pd.read_excel(source, sheet_name=sheet_name, header=2)
            df = df.rename(columns=COL_RENAME)
            df = df[df["raw_name"].notna()].copy()

            rows_added = 0
            for _, row in df.iterrows():
                parsed = parse_name(row["raw_name"], stage)
                session.add(
                    RivmItem(
                        stage=stage,
                        nevo_code=_int_or_none(row.get("nevo_code")),
                        raw_name=str(row["raw_name"]),
                        primary_name=parsed["primary_name"] or "",
                        prep_method=parsed["prep_method"],
                        packaging=parsed["packaging"],
                        conditions=parsed["conditions"],
                        nevo_naam_nl=_str_or_none(row.get("nevo_naam_nl")),
                        nevo_name_en=_str_or_none(row.get("nevo_name_en")),
                        nevo_productgroup_nl=_str_or_none(row.get("nevo_productgroup_nl")),
                        nevo_productgroup_en=_str_or_none(row.get("nevo_productgroup_en")),
                        co2_kgco2eq=_float_or_none(row.get("co2_kgco2eq")),
                        so2_kg=_float_or_none(row.get("so2_kg")),
                        p_kg=_float_or_none(row.get("p_kg")),
                        n_kg=_float_or_none(row.get("n_kg")),
                        land_m2a=_float_or_none(row.get("land_m2a")),
                        water_m3=_float_or_none(row.get("water_m3")),
                    )
                )
                rows_added += 1

            print(f"  {stage:13s} sheet={sheet_name!r:28s} rows={rows_added}")
            total += rows_added

        session.commit()

    print()
    print(f"Inserted {total} rows total.")
    print()
    print("Per-stage verification:")
    with Session(engine) as session:
        for stage in STAGE_SHEETS:
            n_rows = session.scalar(
                select(func.count()).select_from(RivmItem).where(RivmItem.stage == stage)
            )
            n_nevo = session.scalar(
                select(func.count(func.distinct(RivmItem.nevo_code))).where(
                    RivmItem.stage == stage
                )
            )
            n_with_co2 = session.scalar(
                select(func.count())
                .select_from(RivmItem)
                .where(RivmItem.stage == stage, RivmItem.co2_kgco2eq.is_not(None))
            )
            print(
                f"  {stage:13s} rows={n_rows:4d}  unique_nevo={n_nevo:4d}  with_co2={n_with_co2:4d}"
            )


if __name__ == "__main__":
    ingest()
