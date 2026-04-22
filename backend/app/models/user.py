"""User-DB ORM models.

All tables live in the Postgres user DB (not the SQLite reference DB).
Inherits from UserBase (app.db.user_base) — deliberately separate from the
reference-DB Base so SQLAlchemy never confuses the two engines.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.user_base import UserBase


class User(SQLAlchemyBaseUserTableUUID, UserBase):
    """Application user.

    Extends fastapi-users' base UUID table with a display name.
    Table name is ``auth_user`` to avoid the PostgreSQL reserved word ``user``.
    """

    __tablename__ = "auth_user"

    full_name: Mapped[str] = mapped_column(String(200), server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    meals: Mapped[list[Meal]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    procurement_entries: Mapped[list[ProcurementEntry]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Meal(UserBase):
    """A saved meal belonging to one user."""

    __tablename__ = "meal"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("auth_user.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300))
    notes: Mapped[str] = mapped_column(String(1000), server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    # Cached environmental totals — computed at save time from RIVM reference DB
    total_co2_kg:   Mapped[float | None] = mapped_column(Float, nullable=True)
    total_water_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_land_m2a: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_so2_kg:   Mapped[float | None] = mapped_column(Float, nullable=True)
    total_p_kg:     Mapped[float | None] = mapped_column(Float, nullable=True)
    total_n_kg:     Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="meals")
    ingredients: Mapped[list[MealIngredient]] = relationship(
        back_populates="meal",
        cascade="all, delete-orphan",
        order_by="MealIngredient.position",
    )


class MealIngredient(UserBase):
    """One line item within a saved meal.

    ``rivm_item_id`` references the read-only reference DB (not a FK because
    they're in different databases).  ``primary_name`` is stored as a snapshot
    so the history page can display names without cross-DB joins.
    """

    __tablename__ = "meal_ingredient"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    meal_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("meal.id", ondelete="CASCADE"),
        index=True,
    )
    rivm_item_id: Mapped[int] = mapped_column(Integer, index=True)
    primary_name: Mapped[str] = mapped_column(String(300))   # snapshot for display
    amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))             # g|kg|ml|L|piece
    position: Mapped[int] = mapped_column(Integer, default=0)  # display ordering

    meal: Mapped[Meal] = relationship(back_populates="ingredients")


class ProcurementEntry(UserBase):
    """A saved procurement order / purchase list belonging to one user."""

    __tablename__ = "procurement_entry"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("auth_user.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(300))
    notes: Mapped[str] = mapped_column(String(1000), server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    # Cached environmental totals — computed at save time from RIVM reference DB
    total_co2_kg:   Mapped[float | None] = mapped_column(Float, nullable=True)
    total_water_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_land_m2a: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_so2_kg:   Mapped[float | None] = mapped_column(Float, nullable=True)
    total_p_kg:     Mapped[float | None] = mapped_column(Float, nullable=True)
    total_n_kg:     Mapped[float | None] = mapped_column(Float, nullable=True)

    user: Mapped[User] = relationship(back_populates="procurement_entries")
    items: Mapped[list[ProcurementItem]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="ProcurementItem.position",
    )


class ProcurementItem(UserBase):
    """One line item in a saved procurement entry.

    Always references a ``distribution``-stage RIVM item.  ``primary_name``
    is stored as a snapshot so the history list renders without cross-DB joins.
    """

    __tablename__ = "procurement_item"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("procurement_entry.id", ondelete="CASCADE"),
        index=True,
    )
    rivm_item_id: Mapped[int] = mapped_column(Integer, index=True)
    primary_name: Mapped[str] = mapped_column(String(300))   # snapshot for display
    amount: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10))             # g|kg|ml|L|piece
    position: Mapped[int] = mapped_column(Integer, default=0)

    entry: Mapped[ProcurementEntry] = relationship(back_populates="items")
