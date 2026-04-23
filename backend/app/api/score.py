"""On-demand EAT-Lancet scoring endpoint.

Called by the frontend *before* a meal/procurement is saved so the scores can
be shown in the live results panel.  No auth required — the reference DB is
read-only and contains no user data.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.scoring.scorers import compute_scores_async

router = APIRouter(prefix="/api/score", tags=["scoring"])


class ScoreItem(BaseModel):
    rivm_item_id: int
    amount: float
    unit: str    # g | kg | ml | L | piece


class ScoreRequest(BaseModel):
    items: list[ScoreItem]


class ScoreResponse(BaseModel):
    eat_lancet: float
    planetary_health: float
    dimension_levels: dict[str, int]


@router.post("", response_model=ScoreResponse)
async def score_items(body: ScoreRequest) -> ScoreResponse:
    """Compute EAT-Lancet Alignment and Planetary Health scores for a list of items.

    Returns scores on a 0–100 scale plus the raw 0–4 levels for each dimension.
    No authentication required; the reference DB is read-only.
    """
    result = await compute_scores_async(
        [(item.rivm_item_id, item.amount, item.unit) for item in body.items]
    )
    return ScoreResponse(
        eat_lancet=result["eat_lancet"],
        planetary_health=result["planetary_health"],
        dimension_levels=result["dimension_levels"],
    )
