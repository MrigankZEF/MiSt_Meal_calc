"""EAT-Lancet Alignment and Planetary Health Meal scoring.

Formulas from VISION.md §6.1, weights from Willett et al. (2019):

  EAT-Lancet Alignment Score (EAT)  — weights sum 100:
    plant_volume 18 · whole_grains 16 · legumes 16
    animal_moderation 18 · low_processing 16 · veg_diversity 16

  Planetary Health Meal Score (PHS) — weights sum 100:
    plant_volume 24 · whole_grains 14 · legumes 18
    low_red_meat 24 · low_processing 12 · fruit_nuts 8

Each dimension level (0–4) contributes: (level / 4) × weight.
Final score = sum, clamped to [0, 100].

Interpretation bands (shared):
  80–100 Strong · 60–79 Fair · 40–59 Mixed · <40 Weak
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.services.footprint.compute import _to_kg
from app.services.scoring.buckets import get_item_buckets
from app.services.scoring.level_mapping import BucketWeights, dimension_levels

# ── Score weights ─────────────────────────────────────────────────────────────

EAT_WEIGHTS: dict[str, float] = {
    "plant_volume":      18.0,
    "whole_grains":      16.0,
    "legumes":           16.0,
    "animal_moderation": 18.0,
    "low_processing":    16.0,
    "veg_diversity":     16.0,
}

PLANETARY_WEIGHTS: dict[str, float] = {
    "plant_volume":   24.0,
    "whole_grains":   14.0,
    "legumes":        18.0,
    "low_red_meat":   24.0,
    "low_processing": 12.0,
    "fruit_nuts":      8.0,
}

BAND_LABELS: list[tuple[float, str]] = [
    (80.0, "Strong"),
    (60.0, "Fair"),
    (40.0, "Mixed"),
    (0.0,  "Weak"),
]


def score_band(score: float) -> str:
    for threshold, label in BAND_LABELS:
        if score >= threshold:
            return label
    return "Weak"


def _apply_weights(levels: dict[str, int], weights: dict[str, float]) -> float:
    total = sum((levels[dim] / 4.0) * w for dim, w in weights.items())
    return max(0.0, min(100.0, total))


# ── Core computation (sync, needs reference DB session) ───────────────────────

def _build_bucket_weights(
    session: Session,
    items: list[tuple[int, float, str]],  # (rivm_item_id, amount, unit)
) -> BucketWeights:
    """Convert a list of (rivm_item_id, amount, unit) into BucketWeights."""
    if not items:
        return BucketWeights()

    rivm_ids = [i[0] for i in items]
    item_buckets = get_item_buckets(session, rivm_ids)

    bw = BucketWeights()
    seen_plant_veg_nevo: set[int] = set()

    for rivm_id, amount, unit in items:
        kg = _to_kg(amount, unit)
        nevo_code, bucket = item_buckets.get(rivm_id, (None, "other"))

        bw.bucket_kg[bucket] = bw.bucket_kg.get(bucket, 0.0) + kg
        bw.total_kg += kg

        if bucket == "plant_veg" and nevo_code is not None:
            seen_plant_veg_nevo.add(nevo_code)

    bw.distinct_plant_veg = len(seen_plant_veg_nevo)
    return bw


def compute_scores(
    session: Session,
    items: list[tuple[int, float, str]],
) -> dict[str, float | dict[str, int]]:
    """Compute EAT-Lancet and Planetary Health scores synchronously.

    Returns::

        {
            "eat_lancet":      float,        # 0–100
            "planetary_health": float,       # 0–100
            "dimension_levels": {str: int},  # 0–4 per dimension
        }
    """
    bw = _build_bucket_weights(session, items)
    levels = dimension_levels(bw)

    return {
        "eat_lancet":       _apply_weights(levels, EAT_WEIGHTS),
        "planetary_health": _apply_weights(levels, PLANETARY_WEIGHTS),
        "dimension_levels": levels,
    }


async def compute_scores_async(
    items: list[tuple[int, float, str]],
) -> dict[str, float | dict[str, int]]:
    """Async-safe wrapper: runs ``compute_scores`` in a thread pool."""
    from app.db.reference_session import ReferenceSession

    def _run() -> dict[str, float | dict[str, int]]:
        with ReferenceSession() as session:
            return compute_scores(session, items)

    return await asyncio.to_thread(_run)
