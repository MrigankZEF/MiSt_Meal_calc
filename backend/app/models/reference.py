from typing import Any

from sqlalchemy import JSON, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RivmItem(Base):
    __tablename__ = "rivm_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    stage: Mapped[str] = mapped_column(String, nullable=False)
    nevo_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    primary_name: Mapped[str] = mapped_column(String, nullable=False)
    prep_method: Mapped[str | None] = mapped_column(String, nullable=True)
    packaging: Mapped[str | None] = mapped_column(String, nullable=True)
    conditions: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)

    nevo_naam_nl: Mapped[str | None] = mapped_column(String, nullable=True)
    nevo_name_en: Mapped[str | None] = mapped_column(String, nullable=True)
    nevo_productgroup_nl: Mapped[str | None] = mapped_column(String, nullable=True)
    nevo_productgroup_en: Mapped[str | None] = mapped_column(String, nullable=True)

    co2_kgco2eq: Mapped[float | None] = mapped_column(Float, nullable=True)
    so2_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    p_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    land_m2a: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_m3: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_rivm_item_stage", "stage"),
        Index("ix_rivm_item_nevo_code", "nevo_code"),
        Index("ix_rivm_item_primary_name", "primary_name"),
    )

    def __repr__(self) -> str:
        return (
            f"RivmItem(id={self.id}, stage={self.stage!r}, "
            f"primary_name={self.primary_name!r}, prep_method={self.prep_method!r})"
        )


class NevoNutrition(Base):
    """Per-100 g nutrition from NEVO2025. Joined to RivmItem via nevo_code.

    Curated macronutrient columns are surfaced as typed fields; the full
    148-column original row is preserved verbatim in `raw_nutrients` (JSON)
    so nothing is lost.
    """

    __tablename__ = "nevo_nutrition"

    nevo_code: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Identification
    dutch_name: Mapped[str | None] = mapped_column(String, nullable=True)
    english_name: Mapped[str | None] = mapped_column(String, nullable=True)
    synonym: Mapped[str | None] = mapped_column(String, nullable=True)
    food_group_nl: Mapped[str | None] = mapped_column(String, nullable=True)
    food_group_en: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity: Mapped[str | None] = mapped_column(String, nullable=True)  # 'per 100g'

    # Energy
    kj: Mapped[float | None] = mapped_column(Float, nullable=True)
    kcal: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Macros
    water_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_plant_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_animal_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_saturated_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_mono_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_poly_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carb_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    sugar_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    starch_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fibre_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    alcohol_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Select minerals (the rest live in raw_nutrients)
    sodium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    calcium_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    iron_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vitamin_c_mg: Mapped[float | None] = mapped_column(Float, nullable=True)
    vitamin_d_ug: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lossless original row (all 148 columns, strings and floats)
    raw_nutrients: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_nevo_nutrition_english_name", "english_name"),
        Index("ix_nevo_nutrition_dutch_name", "dutch_name"),
    )

    def __repr__(self) -> str:
        return (
            f"NevoNutrition(nevo_code={self.nevo_code}, "
            f"english_name={self.english_name!r}, kcal={self.kcal})"
        )
