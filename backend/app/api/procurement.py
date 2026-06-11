"""Procurement CRUD — all endpoints require a valid JWT."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import current_active_user
from app.db.user_session import get_async_user_session
from app.models.user import ProcurementEntry, ProcurementItem, User
from app.schemas.procurement import ProcurementIn, ProcurementListItem, ProcurementOut
from app.services.footprint.compute import compute_totals_async
from app.services.scoring.scorers import compute_scores_async

router = APIRouter(prefix="/api/procurement", tags=["procurement"])


class AggregateScoreRequest(BaseModel):
    entry_ids: list[uuid.UUID]


class AggregateScoreResponse(BaseModel):
    eat_lancet: float
    planetary_health: float
    dimension_levels: dict[str, int]
    entry_count: int
    item_count: int


@router.get("", response_model=list[ProcurementListItem])
async def list_procurement(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> list[ProcurementListItem]:
    """Return all procurement entries for the current user, newest first."""
    result = await session.execute(
        select(ProcurementEntry)
        .where(ProcurementEntry.user_id == user.id)
        .options(selectinload(ProcurementEntry.items))
        .order_by(ProcurementEntry.created_at.desc())
    )
    entries = result.scalars().all()
    return [
        ProcurementListItem(
            id=e.id,
            name=e.name,
            notes=e.notes,
            created_at=e.created_at,
            item_count=len(e.items),
            total_co2_kg=e.total_co2_kg,
            total_water_m3=e.total_water_m3,
            total_land_m2a=e.total_land_m2a,
            total_so2_kg=e.total_so2_kg,
            total_p_kg=e.total_p_kg,
            total_n_kg=e.total_n_kg,
            eat_lancet_score=e.eat_lancet_score,
            planetary_health_score=e.planetary_health_score,
        )
        for e in entries
    ]


@router.post("", response_model=ProcurementOut, status_code=status.HTTP_201_CREATED)
async def create_procurement(
    body: ProcurementIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> ProcurementEntry:
    """Save a procurement entry."""
    item_tuples = [(item.rivm_item_id, item.amount, item.unit) for item in body.items]
    totals, scores = await asyncio.gather(
        compute_totals_async(item_tuples),
        compute_scores_async(item_tuples),
    )
    entry = ProcurementEntry(
        user_id=user.id,
        name=body.name.strip() or "Untitled order",
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        total_co2_kg=totals["co2_kg"],
        total_water_m3=totals["water_m3"],
        total_land_m2a=totals["land_m2a"],
        total_so2_kg=totals["so2_kg"],
        total_p_kg=totals["p_kg"],
        total_n_kg=totals["n_kg"],
        eat_lancet_score=scores["eat_lancet"],
        planetary_health_score=scores["planetary_health"],
        items=[
            ProcurementItem(
                rivm_item_id=item.rivm_item_id,
                primary_name=item.primary_name,
                amount=item.amount,
                unit=item.unit,
                position=item.position,
            )
            for item in body.items
        ],
    )
    session.add(entry)
    await session.commit()
    result = await session.execute(
        select(ProcurementEntry)
        .where(ProcurementEntry.id == entry.id)
        .options(selectinload(ProcurementEntry.items))
    )
    return result.scalar_one()


@router.post("/aggregate-score", response_model=AggregateScoreResponse)
async def aggregate_score(
    body: AggregateScoreRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> AggregateScoreResponse:
    """Score the *pooled* items of several procurement entries as one basket.

    The frontend passes the IDs of the orders currently in view (after the
    period filter).  We pool every item across those orders — weighted by its
    saved amount — and run the EAT-Lancet scorer once.  Averaging the stored
    per-order scores would be meaningless; pooling the underlying quantities is
    the correct aggregation, mirroring how the environmental totals are summed.
    """
    if not body.entry_ids:
        return AggregateScoreResponse(
            eat_lancet=0.0, planetary_health=0.0,
            dimension_levels={}, entry_count=0, item_count=0,
        )

    result = await session.execute(
        select(ProcurementEntry)
        .where(
            ProcurementEntry.id.in_(body.entry_ids),
            ProcurementEntry.user_id == user.id,
        )
        .options(selectinload(ProcurementEntry.items))
    )
    entries = result.scalars().all()

    item_tuples = [
        (item.rivm_item_id, item.amount, item.unit)
        for entry in entries
        for item in entry.items
    ]
    if not item_tuples:
        return AggregateScoreResponse(
            eat_lancet=0.0, planetary_health=0.0,
            dimension_levels={}, entry_count=len(entries), item_count=0,
        )

    scores = await compute_scores_async(item_tuples)
    return AggregateScoreResponse(
        eat_lancet=scores["eat_lancet"],
        planetary_health=scores["planetary_health"],
        dimension_levels=scores["dimension_levels"],
        entry_count=len(entries),
        item_count=len(item_tuples),
    )


@router.get("/{entry_id}", response_model=ProcurementOut)
async def get_procurement(
    entry_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> ProcurementEntry:
    """Fetch a single procurement entry (must belong to the current user)."""
    result = await session.execute(
        select(ProcurementEntry)
        .where(ProcurementEntry.id == entry_id, ProcurementEntry.user_id == user.id)
        .options(selectinload(ProcurementEntry.items))
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Procurement entry not found")
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_procurement(
    entry_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> None:
    """Delete a procurement entry (must belong to the current user)."""
    result = await session.execute(
        select(ProcurementEntry).where(
            ProcurementEntry.id == entry_id, ProcurementEntry.user_id == user.id
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Procurement entry not found")
    await session.delete(entry)
    await session.commit()
