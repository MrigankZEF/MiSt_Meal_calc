"""Seed ``eat_lancet_tag`` from NEVO food groups + name-pattern overrides.

Run from ``backend/`` after ``ingest_rivm.py`` and ``ingest_nevo.py``:

    source .venv/bin/activate
    python scripts/seed_eat_lancet_tags.py

The script drops and recreates ``eat_lancet_tag`` so it is safe to re-run.

Pass 1 — food_group_en → bucket (broad assignment).
Pass 2 — dutch_name pattern overrides (corrects grains, poultry, oils, juices).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base
from app.db.reference_session import reference_engine, ReferenceSession
from app.models.reference import EatLancetTag, NevoNutrition  # noqa: F401

# ---------------------------------------------------------------------------
# Pass 1: food_group_en → (bucket, confirmed, notes)
# ---------------------------------------------------------------------------
FOOD_GROUP_MAP: dict[str, tuple[str, bool, str]] = {
    "Vegetables":                              ("plant_veg",       True,  ""),
    "Potatoes and tubers":                     ("plant_veg",       True,  ""),
    "Fruits":                                  ("plant_fruit",     True,  ""),
    "Legumes":                                 ("legume",          True,  ""),
    "Nuts and seeds":                          ("nut_seed",        True,  ""),
    "Bread":                                   ("refined_grain",   False, "review: may include whole-grain bread"),
    "Cereal products and types of flour":      ("refined_grain",   False, "review: may include whole-grain products"),
    "Eggs":                                    ("egg",             True,  ""),
    "Fish, crustacean and shellfish":          ("fish",            True,  ""),
    "Cheese":                                  ("dairy",           True,  ""),
    "Milk and milk products":                  ("dairy",           True,  ""),
    "Cold meat cuts":                          ("red_meat",        True,  ""),
    "Meat and poultry":                        ("red_meat",        False, "review: poultry items should be white_meat"),
    "Meat substitutes and dairy substitutes":  ("other",           False, "review: likely plant protein"),
    "Fats and oils":                           ("oil_healthy",     False, "review: saturated fats should be oil_unhealthy"),
    "Pastry and biscuits":                     ("ultra_processed", True,  ""),
    "Sugar, sweets and sweet sauces":          ("sugar_sweet",     True,  ""),
    "Savoury snacks":                          ("ultra_processed", True,  ""),
    "Non-alcoholic beverages":                 ("other",           True,  ""),
    "Alcoholic beverages":                     ("other",           True,  ""),
    "Savoury sauces":                          ("other",           True,  ""),
    "Savoury bread spreads":                   ("other",           True,  ""),
    "Soups":                                   ("other",           True,  ""),
    "Herbs and spices":                        ("other",           True,  ""),
    "Miscellaneous foods":                     ("other",           True,  ""),
    "Mixed dishes":                            ("other",           False, "review: composition varies"),
    "Foods for special nutritional use":       ("other",           True,  ""),
}

CONFIRMED_BY = "auto:food_group_en"

# ---------------------------------------------------------------------------
# Pass 2: dutch_name substring overrides
# Each entry: (pattern, target_bucket, only_if_bucket_is, confirmed, notes)
#   pattern            — lowercase substring to match in dutch_name
#   target_bucket      — override to this bucket
#   only_if_bucket_is  — frozenset of current buckets to guard against false positives
#                        (None = apply regardless of current bucket)
#   confirmed          — True if override is high-confidence
#   notes              — stored in tag.notes
# ---------------------------------------------------------------------------
_ANY = None  # sentinel: override applies regardless of current bucket

NAME_OVERRIDES: list[tuple[str, str, frozenset[str] | None, bool, str]] = [
    # ── Whole grains ──────────────────────────────────────────────────────
    # Only upgrade from grain / other buckets — never override veg or meat
    ("volkoren",     "whole_grain", frozenset({"refined_grain", "other"}), True, "whole-grain"),
    ("zilvervlies",  "whole_grain", frozenset({"refined_grain", "other"}), True, "brown rice"),
    ("havervlok",    "whole_grain", frozenset({"refined_grain", "other"}), True, "oat flakes"),
    ("haver vlok",   "whole_grain", frozenset({"refined_grain", "other"}), True, "oat flakes"),
    ("haverout",     "whole_grain", frozenset({"refined_grain", "other"}), True, "oats"),
    ("boekweit",     "whole_grain", frozenset({"refined_grain", "other"}), True, "buckwheat"),
    ("gerst hele",   "whole_grain", frozenset({"refined_grain", "other"}), True, "hulled barley"),
    ("kiemen tarwe", "whole_grain", frozenset({"refined_grain", "other"}), True, "wheat germ"),
    ("meergranen",   "whole_grain", frozenset({"refined_grain", "other"}), True, "multigrain"),
    ("grutten",      "whole_grain", frozenset({"refined_grain", "other"}), True, "groats"),
    # ── Poultry — override red_meat only ──────────────────────────────────
    ("kip",          "white_meat",  frozenset({"red_meat"}), True, "chicken"),
    ("kalkoen",      "white_meat",  frozenset({"red_meat"}), True, "turkey"),
    # ── Unhealthy fats — override oil_healthy only ────────────────────────
    ("boter",        "oil_unhealthy", frozenset({"oil_healthy"}), True, "butter"),
    ("frituur",      "oil_unhealthy", frozenset({"oil_healthy"}), True, "frying fat"),
    ("palmvet",      "oil_unhealthy", frozenset({"oil_healthy"}), True, "palm fat"),
    # ── Peanut butter — anywhere it appears ───────────────────────────────
    ("pindakaas",    "nut_seed",    _ANY, True, "peanut butter"),
    # ── Soy / plant drinks — in dairy or other ────────────────────────────
    ("sojamelk",     "legume",      frozenset({"dairy", "other"}), True, "soy milk"),
    ("sojadrink",    "legume",      frozenset({"dairy", "other"}), True, "soy drink"),
    ("soja drink",   "legume",      frozenset({"dairy", "other"}), True, "soy drink"),
    ("soyadrink",    "legume",      frozenset({"dairy", "other"}), True, "soy drink"),
    # ── Vegetarian/tofu/tempeh — override other ───────────────────────────
    ("tofu",         "legume",      frozenset({"other"}), True, "tofu"),
    ("tempeh",       "legume",      frozenset({"other"}), True, "tempeh"),
    ("seitan",       "legume",      frozenset({"other"}), True, "seitan"),
    ("vegetarisch",  "legume",      frozenset({"other"}), True, "vegetarian substitute"),
    ("vleesverv",    "legume",      frozenset({"other"}), True, "meat substitute"),
]

# Fruit juice: override Non-alcoholic beverages that contain "sap"
# Applied separately (needs food_group check, not just name).
_JUICE_RE = re.compile(r"\bsap\b|vruchtensap|fruitsap")


def _apply_name_overrides(
    dutch_name: str,
    food_group_en: str,
    current_bucket: str,
) -> tuple[str, bool, str] | None:
    """Return (bucket, confirmed, notes) if a name override fires, else None."""
    name_lc = (dutch_name or "").lower()

    for pattern, target, guard, confirmed, notes in NAME_OVERRIDES:
        if pattern not in name_lc:
            continue
        if guard is not None and current_bucket not in guard:
            continue
        return target, confirmed, f"name-override: {notes or pattern}"

    # Fruit juice override (requires Non-alcoholic beverages group)
    if current_bucket == "other" and food_group_en == "Non-alcoholic beverages":
        if _JUICE_RE.search(name_lc):
            return "plant_fruit", True, "name-override: fruit juice"

    return None


def run() -> None:
    with reference_engine.begin() as conn:
        EatLancetTag.__table__.drop(conn, checkfirst=True)
        EatLancetTag.__table__.create(conn)
    print("eat_lancet_tag table (re)created.")

    with ReferenceSession() as session:
        nutrition_rows = session.query(NevoNutrition).all()
        tags: list[EatLancetTag] = []
        unknown_groups: set[str] = set()
        override_count = 0

        for row in nutrition_rows:
            group = row.food_group_en or ""
            if group in FOOD_GROUP_MAP:
                bucket, confirmed, notes = FOOD_GROUP_MAP[group]
            else:
                bucket, confirmed, notes = "other", True, f"unmapped group: {group!r}"
                if group:
                    unknown_groups.add(group)

            # Pass 2: name-based override
            override = _apply_name_overrides(row.dutch_name or "", group, bucket)
            if override:
                bucket, confirmed, notes = override
                override_count += 1

            tags.append(EatLancetTag(
                nevo_code=row.nevo_code,
                bucket=bucket,
                notes=notes,
                confirmed_by=CONFIRMED_BY,
                confirmed=confirmed,
            ))

        session.bulk_save_objects(tags)
        session.commit()

    total        = len(tags)
    needs_review = sum(1 for t in tags if not t.confirmed)
    auto_ok      = total - needs_review

    print(f"Inserted {total} tags.")
    print(f"  Confirmed (no review needed): {auto_ok}")
    print(f"  Needs review:                 {needs_review}")
    print(f"  Name-pattern overrides:       {override_count}")
    if unknown_groups:
        print(f"  Unknown food groups (→ other): {sorted(unknown_groups)}")

    # Bucket distribution
    from collections import Counter
    bucket_counts = Counter(t.bucket for t in tags)
    print("\nBucket distribution:")
    for b, cnt in sorted(bucket_counts.items()):
        print(f"  {b:<20} {cnt:4d}")

    # RIVM coverage
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
