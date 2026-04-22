"""Ingredient search + grouped-variant assembly.

Two modes:

- **meal**: pulls `retail` + `consumption` stage rows. Groups by NEVO code
  (falling back to primary_name for rows without a NEVO code). Each group
  exposes one variant per row — e.g. `supermarket`, `boiling`, `pan frying`.
- **procurement**: pulls `distribution` stage rows only. One row per NEVO code,
  so each group has exactly one variant.

# Scoring

Tiered, deterministic, group-level (not per-row). The *group* is the NEVO
entry; we don't care about which variant row matches the query, only that
the food group is the right one.

1. **Exact primary-name match** → 120.
2. **Every query stem present as a token in primary name** → 100, minus a
   curated penalty if the primary carries `PROCESSED_WORDS` (e.g. 'starch',
   'sauce', 'juice', 'cake') that denote a *distinct* processed food, minus
   a mild length penalty so `Potato` outranks `Potatoes, w skin` for query
   `potato`.
3. **Partial token overlap** (some query stems in primary) → 65 + 8 per
   overlap, with the same modifier penalty.
4. **Fuzzy fallback** on primary (token_set_ratio) and then on
   `primary + nevo_name_en + nevo_naam_nl` (WRatio, dampened) — rescues
   typos and Dutch-vs-English queries. Typo/cross-lang matches can't beat
   a real stem-subset hit.

Stemming is intentionally minimal — strip trailing `ies`/`es`/`s` — enough
for `potato` ↔ `potatoes`, not enough to conflate unrelated words.

This matches v1's retrieval feel (the v1 UX was "okay" on named foods),
but group-level instead of row-level so long pipe-delimited variant rows
can't crowd the result list.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reference import RivmItem

STAGES_BY_MODE: dict[str, tuple[str, ...]] = {
    # P5 decision: meal mode shows retail-only ("as bought" baseline).
    # Consumption variants are intentionally hidden to avoid cooking-energy
    # double-counting across ingredients.  All consumption rows remain in the
    # DB and this dict entry can be restored to ("retail", "consumption") when
    # a proper meal-level cooking-energy widget is added in P7 (see VISION §10.1).
    "meal": ("retail",),
    "procurement": ("distribution",),
}

MIN_SCORE = 45

# Words inside a primary_name that signal a *distinct processed product*,
# not a prep-method variant of the queried food. Prep methods live in
# `prep_method`, so if these appear in primary_name the row is its own
# food (e.g. "Potato starch" vs "Potatoes"). Penalise their extra
# presence when the query doesn't mention them.
_PROCESSED_WORDS_RAW: frozenset[str] = frozenset(
    {
        "starch",
        "powder",
        "extract",
        "juice",
        "sauce",
        "soup",
        "paste",
        "spread",
        "cream",
        "yoghurt",
        "yogurt",
        "pudding",
        "cake",
        "biscuit",
        "bread",
        "roll",
        "pasta",
        "noodle",
        "nugget",
        "nuggets",
        "crisps",
        "chips",
        "schnitzel",
        "flour",
        "syrup",
        "flakes",
        "ketchup",
    }
)


def normalize(text: str | None) -> str:
    if not text:
        return ""
    t = text.lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(token: str) -> str:
    """Strip common English plural suffixes. Deliberately minimal."""
    for suffix in ("ies", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _stems(text: str) -> set[str]:
    return {_stem(t) for t in text.split() if t}


# Pre-stem the blocklist so plural forms ('crisps' → 'crisp', 'flakes' →
# 'flake', 'nuggets' → 'nugget') match against stemmed candidate tokens.
PROCESSED_WORDS: frozenset[str] = frozenset(_stem(w) for w in _PROCESSED_WORDS_RAW)


def variant_label(row: RivmItem) -> str:
    """UI-facing label for a single variant card.

    Packaging is appended (separated by ' · ') whenever the packaging value
    is meaningful (i.e. not 'Not packed'), so that variants that share the
    same preparation method but differ only in packaging are distinguishable
    in the UI (e.g. 'boiling · Food can' vs 'boiling · Glass jar - 720 ml').
    """
    if row.stage == "distribution":
        base = "distribution"
    elif row.stage == "retail":
        base = "as bought"
    else:
        base = row.prep_method or "unspecified"

    pkg = (row.packaging or "").strip()
    if pkg and pkg.lower() != "not packed":
        return f"{base} · {pkg}"
    return base


@dataclass
class _Group:
    primary_name: str
    nevo_code: int | None
    nevo_naam_nl: str | None
    nevo_name_en: str | None
    nevo_productgroup_nl: str | None
    nevo_productgroup_en: str | None
    rows: list[RivmItem] = field(default_factory=list)


@dataclass
class ScoredGroup:
    score: float
    group: _Group
    # Tiebreaker: primary_name starts with a word that's in the query.
    # RIVM names its foods head-noun-first ("Chicken fillet"), so this
    # signal cleanly demotes oddities like "Eggs chicken" for query
    # "chicken" without touching the score tiers.
    primary_leads: bool = False


def _group_key(row: RivmItem) -> tuple[str, int | str]:
    if row.nevo_code is not None:
        return ("nevo", row.nevo_code)
    return ("name", row.primary_name.lower())


def _variant_sort_key(row: RivmItem) -> tuple[int, str]:
    # Retail first (the "raw" baseline), then consumption rows alphabetically.
    stage_rank = {"distribution": 0, "retail": 0, "consumption": 1}.get(row.stage, 2)
    return stage_rank, (row.prep_method or "")


def _tier_score(query_norm: str, query_stems: set[str], candidate_norm: str) -> float:
    """Score a single candidate string with the tiered exact/subset/overlap
    ladder. Returns 0 if no tier matched (caller will try fuzzy fallback)."""
    if not candidate_norm:
        return 0.0

    candidate_stems = _stems(candidate_norm)
    extra_stems = candidate_stems - query_stems
    has_processed = bool(extra_stems & PROCESSED_WORDS)
    length_penalty = min(12, len(extra_stems) * 2)

    # Tier 1: exact string
    if candidate_norm == query_norm:
        return 120.0

    # Tier 2: every query stem present as a stemmed token in candidate
    if query_stems.issubset(candidate_stems):
        score = 100.0 - length_penalty
        if has_processed:
            score -= 25.0
        return score

    # Tier 3: partial stem overlap
    overlap = query_stems & candidate_stems
    if overlap:
        score = 65.0 + 8.0 * len(overlap) - length_penalty
        if has_processed:
            score -= 20.0
        return score

    return 0.0


def _score_group(query_norm: str, group: _Group) -> tuple[float, bool]:
    """Return (score, primary_leads). Score roughly in [0, 120]; 0 = reject.

    Scores against three candidate strings — `primary_name`,
    `nevo_name_en`, `nevo_naam_nl` — and keeps the max. Cross-language
    queries (e.g. `aardappel`) resolve via the NL name. Falls back to
    rapidfuzz only when every tier candidate comes up empty.
    """
    query_stems = _stems(query_norm)
    if not query_stems:
        return 0.0, False

    primary_norm = normalize(group.primary_name)
    en_norm = normalize(group.nevo_name_en)
    nl_norm = normalize(group.nevo_naam_nl)

    candidates = [c for c in (primary_norm, en_norm, nl_norm) if c]
    if not candidates:
        return 0.0, False

    best = 0.0
    for c in candidates:
        s = _tier_score(query_norm, query_stems, c)
        if s > best:
            best = s

    # First-token signal uses the *primary* name only — it's the RIVM
    # canonical label and conventionally head-noun-first.
    primary_first_stem = _stem(primary_norm.split()[0]) if primary_norm else ""
    primary_leads = primary_first_stem in query_stems

    if best > 0:
        return best, primary_leads

    # Fuzzy fallbacks (only when no tier matched). Tight against primary
    # (typos), broader against combined haystack (cross-lang rescue).
    ratio = fuzz.token_set_ratio(query_norm, primary_norm)
    if ratio >= 78:
        return ratio * 0.70, primary_leads

    haystack = " ".join(candidates)
    wratio = fuzz.WRatio(query_norm, haystack)
    if wratio >= 82:
        return wratio * 0.55, primary_leads

    return 0.0, primary_leads


def search_ingredients(
    session: Session,
    mode: str,
    query: str,
    limit: int = 10,
) -> list[ScoredGroup]:
    if mode not in STAGES_BY_MODE:
        raise ValueError(f"unknown mode: {mode!r}")

    qn = normalize(query)
    if not qn:
        return []

    stages = STAGES_BY_MODE[mode]
    rows = (
        session.execute(select(RivmItem).where(RivmItem.stage.in_(stages)))
        .scalars()
        .all()
    )

    groups: dict[tuple[str, int | str], _Group] = {}
    for r in rows:
        key = _group_key(r)
        g = groups.get(key)
        if g is None:
            g = _Group(
                primary_name=r.primary_name,
                nevo_code=r.nevo_code,
                nevo_naam_nl=r.nevo_naam_nl,
                nevo_name_en=r.nevo_name_en,
                nevo_productgroup_nl=r.nevo_productgroup_nl,
                nevo_productgroup_en=r.nevo_productgroup_en,
            )
            groups[key] = g
        g.rows.append(r)

    scored: list[ScoredGroup] = []
    for g in groups.values():
        score, primary_leads = _score_group(qn, g)
        if score < MIN_SCORE:
            continue
        scored.append(ScoredGroup(score=score, group=g, primary_leads=primary_leads))

    # Sort: score desc → primary_leads first → shorter primary_name first.
    scored.sort(
        key=lambda s: (-s.score, not s.primary_leads, len(s.group.primary_name))
    )

    for s in scored:
        s.group.rows.sort(key=_variant_sort_key)

    return scored[:limit]
