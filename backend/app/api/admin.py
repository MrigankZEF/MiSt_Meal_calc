"""Admin endpoints — EAT-Lancet tag review.

Requires a valid JWT (any logged-in user for now; add role check when
multi-tenant orgs land in a future phase).

GET  /api/admin/eat-lancet          — list all tags with NEVO names + food group
PATCH /api/admin/eat-lancet/{code}  — update bucket / confirmed status
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import current_active_user
from app.db.reference_session import get_reference_session
from app.models.reference import EatLancetTag, NevoNutrition
from app.models.user import User
from app.services.scoring.buckets import BUCKETS

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class EatLancetTagOut(BaseModel):
    nevo_code: int
    bucket: str
    notes: str
    confirmed_by: str | None
    confirmed: bool
    # Joined from nevo_nutrition
    dutch_name: str | None = None
    english_name: str | None = None
    food_group_en: str | None = None


class EatLancetTagUpdate(BaseModel):
    bucket: str
    notes: str = ""
    confirmed: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/eat-lancet", response_model=list[EatLancetTagOut])
def list_eat_lancet_tags(
    needs_review: bool = False,
    _user: User = Depends(current_active_user),
    ref_session: Session = Depends(get_reference_session),
) -> list[EatLancetTagOut]:
    """List EAT-Lancet tags.

    Pass ``?needs_review=true`` to show only unconfirmed entries.
    Results are sorted: unconfirmed first, then by food_group_en, then dutch_name.
    """
    query = ref_session.query(EatLancetTag, NevoNutrition).outerjoin(
        NevoNutrition, EatLancetTag.nevo_code == NevoNutrition.nevo_code
    )
    if needs_review:
        query = query.filter(EatLancetTag.confirmed == False)  # noqa: E712

    rows = query.all()
    # Sort: unconfirmed first, then food group, then name
    rows.sort(key=lambda r: (r[0].confirmed, r[1].food_group_en or "", r[1].dutch_name or ""))

    return [
        EatLancetTagOut(
            nevo_code=tag.nevo_code,
            bucket=tag.bucket,
            notes=tag.notes,
            confirmed_by=tag.confirmed_by,
            confirmed=tag.confirmed,
            dutch_name=nut.dutch_name if nut else None,
            english_name=nut.english_name if nut else None,
            food_group_en=nut.food_group_en if nut else None,
        )
        for tag, nut in rows
    ]


@router.patch("/eat-lancet/{nevo_code}", response_model=EatLancetTagOut)
def update_eat_lancet_tag(
    nevo_code: int,
    body: EatLancetTagUpdate,
    user: User = Depends(current_active_user),
    ref_session: Session = Depends(get_reference_session),
) -> EatLancetTagOut:
    """Update the bucket and confirmation status for a NEVO code."""
    if body.bucket not in BUCKETS:
        raise HTTPException(status_code=422, detail=f"Unknown bucket: {body.bucket!r}")

    tag = ref_session.query(EatLancetTag).filter(EatLancetTag.nevo_code == nevo_code).first()
    if tag is None:
        raise HTTPException(status_code=404, detail=f"No tag for nevo_code={nevo_code}")

    tag.bucket = body.bucket
    tag.notes = body.notes
    tag.confirmed = body.confirmed
    tag.confirmed_by = str(user.email) if body.confirmed else tag.confirmed_by
    ref_session.commit()

    nut = ref_session.query(NevoNutrition).filter(NevoNutrition.nevo_code == nevo_code).first()
    return EatLancetTagOut(
        nevo_code=tag.nevo_code,
        bucket=tag.bucket,
        notes=tag.notes,
        confirmed_by=tag.confirmed_by,
        confirmed=tag.confirmed,
        dutch_name=nut.dutch_name if nut else None,
        english_name=nut.english_name if nut else None,
        food_group_en=nut.food_group_en if nut else None,
    )
