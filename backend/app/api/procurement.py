"""Procurement CRUD — all endpoints require a valid JWT."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import current_active_user
from app.db.user_session import get_async_user_session
from app.models.user import ProcurementEntry, ProcurementItem, User
from app.schemas.procurement import ProcurementIn, ProcurementListItem, ProcurementOut
from app.services.footprint.compute import compute_totals_async

router = APIRouter(prefix="/api/procurement", tags=["procurement"])


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
    totals = await compute_totals_async(
        [(item.rivm_item_id, item.amount, item.unit) for item in body.items],
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
