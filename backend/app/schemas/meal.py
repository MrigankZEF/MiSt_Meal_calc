"""Meal Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MealIngredientIn(BaseModel):
    rivm_item_id: int
    primary_name: str
    amount: float
    unit: str       # 'g' | 'kg' | 'ml' | 'L' | 'piece'
    position: int = 0


class MealIn(BaseModel):
    name: str
    notes: str = ""
    ingredients: list[MealIngredientIn]


class MealIngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rivm_item_id: int
    primary_name: str
    amount: float
    unit: str
    position: int


class MealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    notes: str
    created_at: datetime
    ingredients: list[MealIngredientOut]


class MealListItem(BaseModel):
    """Compact shape returned by GET /api/meals (no ingredients list)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    notes: str
    created_at: datetime
    ingredient_count: int
