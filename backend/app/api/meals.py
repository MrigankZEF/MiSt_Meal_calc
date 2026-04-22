"""Meal CRUD — all endpoints require a valid JWT."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.api.auth import current_active_user
from app.db.reference_session import get_reference_session
from app.db.user_session import get_async_user_session
from app.models.user import Meal, MealIngredient, User
from app.schemas.meal import MealIn, MealListItem, MealOut
from app.services.footprint.compute import compute_totals

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.get("", response_model=list[MealListItem])
async def list_meals(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> list[MealListItem]:
    """Return all meals for the current user, newest first."""
    result = await session.execute(
        select(Meal)
        .where(Meal.user_id == user.id)
        .options(selectinload(Meal.ingredients))
        .order_by(Meal.created_at.desc())
    )
    meals = result.scalars().all()
    return [
        MealListItem(
            id=m.id,
            name=m.name,
            notes=m.notes,
            created_at=m.created_at,
            ingredient_count=len(m.ingredients),
        )
        for m in meals
    ]


@router.post("", response_model=MealOut, status_code=status.HTTP_201_CREATED)
async def create_meal(
    body: MealIn,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
    ref_session: Session = Depends(get_reference_session),
) -> Meal:
    """Save the current meal state as a named meal."""
    totals = compute_totals(
        ref_session,
        [(ing.rivm_item_id, ing.amount, ing.unit) for ing in body.ingredients],
    )
    meal = Meal(
        user_id=user.id,
        name=body.name.strip() or "Untitled meal",
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        total_co2_kg=totals["co2_kg"],
        total_water_m3=totals["water_m3"],
        total_land_m2a=totals["land_m2a"],
        total_so2_kg=totals["so2_kg"],
        total_p_kg=totals["p_kg"],
        total_n_kg=totals["n_kg"],
        ingredients=[
            MealIngredient(
                rivm_item_id=ing.rivm_item_id,
                primary_name=ing.primary_name,
                amount=ing.amount,
                unit=ing.unit,
                position=ing.position,
            )
            for ing in body.ingredients
        ],
    )
    session.add(meal)
    await session.commit()
    # Re-fetch with selectinload — more reliable than session.refresh
    # for relationships on async SQLite.
    result = await session.execute(
        select(Meal)
        .where(Meal.id == meal.id)
        .options(selectinload(Meal.ingredients))
    )
    return result.scalar_one()


@router.get("/{meal_id}", response_model=MealOut)
async def get_meal(
    meal_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> Meal:
    """Fetch a single saved meal (must belong to the current user)."""
    result = await session.execute(
        select(Meal)
        .where(Meal.id == meal_id, Meal.user_id == user.id)
        .options(selectinload(Meal.ingredients))
    )
    meal = result.scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    return meal


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meal(
    meal_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_user_session),
) -> None:
    """Delete a saved meal (must belong to the current user)."""
    result = await session.execute(
        select(Meal).where(Meal.id == meal_id, Meal.user_id == user.id)
    )
    meal = result.scalar_one_or_none()
    if meal is None:
        raise HTTPException(status_code=404, detail="Meal not found")
    await session.delete(meal)
    await session.commit()
