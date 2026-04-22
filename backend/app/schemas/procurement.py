"""Procurement-entry Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProcurementItemIn(BaseModel):
    rivm_item_id: int
    primary_name: str
    amount: float
    unit: str       # 'g' | 'kg' | 'ml' | 'L' | 'piece'
    position: int = 0


class ProcurementIn(BaseModel):
    name: str
    notes: str = ""
    items: list[ProcurementItemIn]


class ProcurementItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rivm_item_id: int
    primary_name: str
    amount: float
    unit: str
    position: int


class ProcurementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    notes: str
    created_at: datetime
    items: list[ProcurementItemOut]


class ProcurementListItem(BaseModel):
    """Compact shape returned by GET /api/procurement (no items list)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    notes: str
    created_at: datetime
    item_count: int
