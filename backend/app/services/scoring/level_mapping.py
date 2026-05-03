"""Map bucket composition to 0-4 dimension levels.

Each dimension is scored on a 0–4 integer scale.  The thresholds below are
derived from the EAT-Lancet Commission reference diet:
  Willett et al. (2019) "Food in the Anthropocene" — The Lancet, 393(10170).

All weight fractions are computed over the total edible weight of the
meal/procurement in kg (after ``_to_kg()`` unit conversion).

``dimension_levels()`` is the sole public entry point.  It returns a dict
``{dimension_name: level_0_to_4}`` for both EAT-Lancet Alignment and
Planetary Health scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.scoring.buckets import (
    ANIMAL_BUCKETS,
    FRUIT_NUT_BUCKETS,
    PLANT_BUCKETS,
    PROCESSED_BUCKETS,
)


@dataclass
class BucketWeights:
    """Aggregated kg weights per bucket for a meal/procurement.

    ``bucket_kg``  maps bucket → total kg.
    ``distinct_plant_veg`` counts distinct nevo_codes with bucket='plant_veg'
    (used for the vegetable-diversity dimension).
    ``total_kg`` is the sum of all item weights (pre-computed for convenience).
    """

    bucket_kg: dict[str, float] = field(default_factory=dict)
    distinct_plant_veg: int = 0
    total_kg: float = 0.0

    def fraction(self, *buckets: str) -> float:
        """Fraction of total weight in the given bucket(s). Returns 0 if total_kg == 0."""
        if self.total_kg <= 0:
            return 0.0
        return sum(self.bucket_kg.get(b, 0.0) for b in buckets) / self.total_kg


# ── Threshold helpers ─────────────────────────────────────────────────────────

def _level_from_thresholds(value: float, thresholds: list[float]) -> int:
    """Return 0-4 level.  ``thresholds`` = [t1, t2, t3, t4] where:
      value >= t4 → 4, value >= t3 → 3, …, value < t1 → 0.
    """
    for level, t in reversed(list(enumerate(thresholds, start=1))):
        if value >= t:
            return level
    return 0


# ── Individual dimension calculators ─────────────────────────────────────────

def _veg_and_fruit(bw: BucketWeights) -> int:
    """Fraction of total weight (excl. oils) from vegetables + fruit.

    Thresholds (% of total weight):
      4 ≥ 75%   3 ≥ 55%   2 ≥ 40%   1 ≥ 25%   0 < 25%
    """
    frac = bw.fraction(*PLANT_BUCKETS)  # PLANT_BUCKETS = {plant_veg, plant_fruit}
    return _level_from_thresholds(frac, [0.25, 0.40, 0.55, 0.75])


def _whole_grains(bw: BucketWeights) -> int:
    """Whole-grain fraction of total meal weight (excl. oils).

    No grains at all → L0 (absence is penalised, not neutral).
    Thresholds (whole_grain_kg / total_kg):
      0% → L0   >0–5% → L1   5–10% → L2   10–20% → L3   ≥20% → L4
    """
    if bw.total_kg <= 0:
        return 0
    frac = bw.bucket_kg.get("whole_grain", 0.0) / bw.total_kg
    return _level_from_thresholds(frac, [1e-9, 0.05, 0.10, 0.20])


def _legumes(bw: BucketWeights) -> int:
    """Fraction of total weight that is legumes.

    Thresholds:
      4 ≥ 20%   3 ≥ 10%   2 ≥ 5%   1 > 0%   0 = 0%
    Source: EAT-Lancet ~50 g legumes / 500 g meal = 10%; generously rewarded.
    """
    frac = bw.fraction("legume")
    return _level_from_thresholds(frac, [1e-9, 0.05, 0.10, 0.20])


def _animal_moderation(bw: BucketWeights) -> int:
    """Inverse: penalises high animal-protein fraction of total weight.

    Animal buckets: red_meat, white_meat, fish, egg, dairy.
    Thresholds (animal fraction):
      4: ≤ 10%   3: ≤ 20%   2: ≤ 35%   1: ≤ 50%   0: > 50%
    Source: EAT-Lancet limits animal protein to ≤28% of calories.
    """
    frac = bw.fraction(*ANIMAL_BUCKETS)
    # Invert: high fraction → low level
    if frac <= 0.10: return 4
    if frac <= 0.20: return 3
    if frac <= 0.35: return 2
    if frac <= 0.50: return 1
    return 0


def _low_processing(bw: BucketWeights) -> int:
    """Fraction of total weight from ultra_processed + sugar_sweet.

    Thresholds:
      4 = 0%   3 < 5%   2 < 15%   1 < 30%   0 ≥ 30%
    """
    frac = bw.fraction(*PROCESSED_BUCKETS)
    if frac == 0.0: return 4
    if frac < 0.05: return 3
    if frac < 0.15: return 2
    if frac < 0.30: return 1
    return 0


def _veg_diversity(bw: BucketWeights) -> int:
    """Count of distinct plant_veg NEVO codes in the meal.

    4 ≥ 4 distinct veg   3 = 3   2 = 2   1 = 1   0 = 0
    """
    n = bw.distinct_plant_veg
    return min(n, 4)


def _low_red_meat(bw: BucketWeights) -> int:
    """Fraction of total weight from red_meat only.

    4 = 0%   3 < 5%   2 < 15%   1 < 30%   0 ≥ 30%
    Source: Planetary Health Diet limits red meat to <14 g/day.
    """
    frac = bw.fraction("red_meat")
    if frac == 0.0: return 4
    if frac < 0.05: return 3
    if frac < 0.15: return 2
    if frac < 0.30: return 1
    return 0


def _fruit_nuts(bw: BucketWeights) -> int:
    """Fraction of total weight from plant_fruit + nut_seed.

    4 ≥ 15%   3 ≥ 8%   2 ≥ 3%   1 > 0%   0 = 0%
    """
    frac = bw.fraction(*FRUIT_NUT_BUCKETS)
    return _level_from_thresholds(frac, [1e-9, 0.03, 0.08, 0.15])


# ── Public entry point ────────────────────────────────────────────────────────

def dimension_levels(bw: BucketWeights) -> dict[str, int]:
    """Return all dimension levels (0–4) for the given bucket weights.

    Keys are stable string names used by the scorer and returned to the client.
    """
    return {
        # EAT-Lancet Alignment dimensions
        "veg_and_fruit":      _veg_and_fruit(bw),
        "whole_grains":       _whole_grains(bw),
        "legumes":            _legumes(bw),
        "animal_moderation":  _animal_moderation(bw),
        "low_processing":     _low_processing(bw),
        "veg_diversity":      _veg_diversity(bw),
        # Additional dimension used only in Planetary Health score
        "low_red_meat":       _low_red_meat(bw),
        "fruit_nuts":         _fruit_nuts(bw),
    }
