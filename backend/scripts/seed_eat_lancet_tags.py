"""Seed ``eat_lancet_tag`` from NEVO food groups.

Run from ``backend/`` after ``ingest_rivm.py`` and ``ingest_nevo.py``:

    source .venv/bin/activate
    python scripts/seed_eat_lancet_tags.py

The script drops and recreates the ``eat_lancet_tag`` table so it is safe to
re-run.  Each NEVO code in ``nevo_nutrition`` gets a bucket based on its
``food_group_en`` value.  Entries that need human review are marked
``confirmed=False``; high-confidence auto-assignments get ``confirmed=True``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``app`` importable from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.db.reference_session import reference_engine, ReferenceSession
from app.models.reference import EatLancetTag, NevoNutrition  # noqa: F401 (registers table)

# ---------------------------------------------------------------------------
# Bucket mapping: food_group_en → (bucket, confirmed, notes)
# ---------------------------------------------------------------------------
# confirmed=True  → high confidence; no human review needed
# confirmed=False → auto-classification is likely correct but edge cases exist;
#                   show in admin review UI for Mrigank to confirm per-item
# ---------------------------------------------------------------------------
FOOD_GROUP_MAP: dict[str, tuple[str, bool, str]] = {
    # Clearly plant-based —————————————————————————————————————
    "Vegetables":                              ("plant_veg",       True,  ""),
    "Potatoes and tubers":                     ("plant_veg",       True,  ""),
    "Fruits":                                  ("plant_fruit",     True,  ""),
    "Legumes":                                 ("legume",          True,  ""),
    "Nuts and seeds":                          ("nut_seed",        True,  ""),
    # Grains — whole vs refined split needed inside group —————
    "Bread":                                   ("refined_grain",   False, "review: may include whole-grain bread"),
    "Cereal products and types of flour":      ("refined_grain",   False, "review: may include whole-grain products"),
    # Animal foods ————————————————————————————————————————————
    "Eggs":                                    ("egg",             True,  ""),
    "Fish, crustacean and shellfish":          ("fish",            True,  ""),
    "Cheese":                                  ("dairy",           True,  ""),
    "Milk and milk products":                  ("dairy",           True,  ""),
    "Cold meat cuts":                          ("red_meat",        True,  ""),
    # Meat and poultry mixed: most NEVO rows here are red meat
    # but poultry should map to white_meat — needs item-level review
    "Meat and poultry":                        ("red_meat",        False, "review: poultry items should be white_meat"),
    # Meat substitutes: protein-rich but plant-based; bucket=other until reviewed
    "Meat substitutes and dairy substitutes":  ("other",           False, "review: likely plant protein, may deserve legume/nut_seed"),
    # Fats — mostly healthy oils, but butter/lard = oil_unhealthy ————
    "Fats and oils":                           ("oil_healthy",     False, "review: saturated fats (butter, lard) should be oil_unhealthy"),
    # Ultra-processed ————————————————————————————————————————
    "Pastry and biscuits":                     ("ultra_processed", True,  ""),
    "Sugar, sweets and sweet sauces":          ("sugar_sweet",     True,  ""),
    "Savoury snacks":                          ("ultra_processed", True,  ""),
    # Other (low scoring impact) ——————————————————————————————
    "Non-alcoholic beverages":                 ("other",           True,  ""),
    "Alcoholic beverages":                     ("other",           True,  ""),
    "Savoury sauces":                          ("other",           True,  ""),
    "Savoury bread spreads":                   ("other",           True,  ""),
    "Soups":                                   ("other",           True,  ""),
    "Herbs and spices":                        ("other",           True,  ""),
    "Miscellaneous foods":                     ("other",           True,  ""),
    "Mixed dishes":                            ("other",           False, "review: composition varies widely"),
    "Foods for special nutritional use":       ("other",           True,  ""),
}

CONFIRMED_BY = "auto:food_group_en"


def run() -> None:
    # Create (or recreate) the eat_lancet_tag table in the reference DB
    with reference_engine.begin() as conn:
        EatLancetTag.__table__.drop(conn, checkfirst=True)
        EatLancetTag.__table__.create(conn)
    print("eat_lancet_tag table (re)created.")

    with ReferenceSession() as session:
        nutrition_rows = session.query(NevoNutrition).all()
        tags: list[EatLancetTag] = []
        unknown_groups: set[str] = set()

        for row in nutrition_rows:
            group = row.food_group_en or ""
            if group in FOOD_GROUP_MAP:
                bucket, confirmed, notes = FOOD_GROUP_MAP[group]
            else:
                bucket, confirmed, notes = "other", True, f"unmapped group: {group!r}"
                if group:
                    unknown_groups.add(group)

            tags.append(EatLancetTag(
                nevo_code=row.nevo_code,
                bucket=bucket,
                notes=notes,
                confirmed_by=CONFIRMED_BY,
                confirmed=confirmed,
            ))

        session.bulk_save_objects(tags)
        session.commit()

    total       = len(tags)
    needs_review = sum(1 for t in tags if not t.confirmed)
    auto_ok      = total - needs_review

    print(f"Inserted {total} tags.")
    print(f"  Confirmed (no review needed): {auto_ok}")
    print(f"  Needs review:                 {needs_review}")
    if unknown_groups:
        print(f"  Unknown food groups (→ other): {sorted(unknown_groups)}")

    # Coverage check: how many RIVM NEVO codes have a tag?
    from app.models.reference import RivmItem
    with ReferenceSession() as session:
        rivm_codes: set[int] = {
            r.nevo_code
            for r in session.query(RivmItem.nevo_code).distinct()
            if r.nevo_code is not None
        }
        tagged = {t.nevo_code for t in tags}
        covered = rivm_codes & tagged
        pct = 100.0 * len(covered) / len(rivm_codes) if rivm_codes else 0.0
        print(f"\nRIVM NEVO coverage: {len(covered)}/{len(rivm_codes)} = {pct:.1f}%")
        if pct >= 90.0:
            print("✓ ≥90% coverage threshold met — scoring is active.")
        else:
            print("✗ Below 90% threshold — scoring will be suppressed.")


if __name__ == "__main__":
    run()
