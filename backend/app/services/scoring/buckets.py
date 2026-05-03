"""EAT-Lancet bucket helpers.

A *bucket* is one of the 16 food-system categories used to classify NEVO items
for EAT-Lancet / Planetary Health scoring.  The canonical source is the
``eat_lancet_tag`` table in the reference DB.

This module provides:
- The set of valid bucket names (``BUCKETS``).
- Convenience groupings used by the level-mapping logic.
- ``get_item_buckets(session, rivm_item_ids)`` — looks up (nevo_code, bucket)
  for a list of rivm_item IDs.  Items without a tag get bucket ``"other"``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.reference import EatLancetTag, RivmItem

# ── Valid bucket names ────────────────────────────────────────────────────────

BUCKETS: frozenset[str] = frozenset({
    "plant_veg",
    "plant_fruit",
    "whole_grain",
    "refined_grain",
    "legume",
    "nut_seed",
    "dairy",
    "red_meat",
    "white_meat",
    "fish",
    "egg",
    "oil_healthy",
    "oil_unhealthy",
    "ultra_processed",
    "sugar_sweet",
    "other",
})

# ── Semantic groupings ────────────────────────────────────────────────────────

PLANT_BUCKETS:    frozenset[str] = frozenset({"plant_veg", "plant_fruit"})
GRAIN_BUCKETS:    frozenset[str] = frozenset({"whole_grain", "refined_grain"})
ANIMAL_BUCKETS:   frozenset[str] = frozenset({"red_meat", "white_meat", "fish", "egg", "dairy"})
PROCESSED_BUCKETS: frozenset[str] = frozenset({"ultra_processed", "sugar_sweet"})
FRUIT_NUT_BUCKETS: frozenset[str] = frozenset({"plant_fruit", "nut_seed"})
OIL_BUCKETS:      frozenset[str] = frozenset({"oil_healthy", "oil_unhealthy"})


# ── Lookup helper ─────────────────────────────────────────────────────────────

def get_item_buckets(
    session: Session,
    rivm_item_ids: list[int],
) -> dict[int, tuple[int | None, str]]:
    """Return ``{rivm_item_id: (nevo_code, bucket)}`` for the given IDs.

    Items whose RIVM row has no nevo_code, or whose nevo_code has no tag, get
    bucket ``"other"``.  This ensures scoring always has a value for every item.
    """
    if not rivm_item_ids:
        return {}

    unique_ids = list(set(rivm_item_ids))

    # Fetch RivmItem rows to get nevo_codes
    rivm_rows: dict[int, int | None] = {
        r.id: r.nevo_code
        for r in session.query(RivmItem).filter(RivmItem.id.in_(unique_ids)).all()
    }

    # Collect non-null nevo_codes and fetch their tags
    nevo_codes = [nc for nc in rivm_rows.values() if nc is not None]
    tag_map: dict[int, str] = {}
    if nevo_codes:
        tags = (
            session.query(EatLancetTag)
            .filter(EatLancetTag.nevo_code.in_(nevo_codes))
            .all()
        )
        tag_map = {t.nevo_code: t.bucket for t in tags}

    result: dict[int, tuple[int | None, str]] = {}
    for rivm_id in rivm_item_ids:
        nevo_code = rivm_rows.get(rivm_id)
        bucket = tag_map.get(nevo_code, "other") if nevo_code is not None else "other"
        result[rivm_id] = (nevo_code, bucket)

    return result
