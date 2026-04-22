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
    total_co2_kg:   float | None = None
    total_water_m3: float | None = None
    total_land_m2a: float | None = None
    total_so2_kg:   float | None = None
    total_p_kg:     float | None = None
    total_n_kg:     float | None = None
    items: list[ProcurementItemOut]


class ProcurementListItem(BaseModel):
    """Compact shape returned by GET /api/procurement (no items list)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    notes: str
    created_at: datetime
    item_count: int
    total_co2_kg:   float | None = None
    total_water_m3: float | None = None
    total_land_m2a: float | None = None
    total_so2_kg:   float | None = None
    total_p_kg:     float | None = None
    total_n_kg:     float | None = None
