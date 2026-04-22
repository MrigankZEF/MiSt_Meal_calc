from typing import Any

from pydantic import BaseModel, ConfigDict


class IngredientVariant(BaseModel):
    """One RIVM row, surfaced as a selectable variant under a group."""

    model_config = ConfigDict(from_attributes=True)

    rivm_item_id: int
    label: str
    stage: str
    prep_method: str | None = None
    packaging: str | None = None
    conditions: str | None = None

    co2_kgco2eq: float | None = None
    so2_kg: float | None = None
    p_kg: float | None = None
    n_kg: float | None = None
    land_m2a: float | None = None
    water_m3: float | None = None


class IngredientGroup(BaseModel):
    """A NEVO-keyed group. One card per group in the UI; user picks a variant."""

    primary_name: str
    nevo_code: int | None = None
    nevo_name_nl: str | None = None
    nevo_name_en: str | None = None
    nevo_productgroup_nl: str | None = None
    nevo_productgroup_en: str | None = None
    score: float
    variants: list[IngredientVariant]


class IngredientSearchResponse(BaseModel):
    mode: str
    query: str
    results: list[IngredientGroup]


class NevoNutritionOut(BaseModel):
    """Curated per-100 g nutrition panel. `raw_nutrients` holds the full
    148-column NEVO row for clients that need the long tail."""

    model_config = ConfigDict(from_attributes=True)

    nevo_code: int
    dutch_name: str | None = None
    english_name: str | None = None
    synonym: str | None = None
    food_group_nl: str | None = None
    food_group_en: str | None = None
    quantity: str | None = None

    kj: float | None = None
    kcal: float | None = None
    water_g: float | None = None
    protein_g: float | None = None
    protein_plant_g: float | None = None
    protein_animal_g: float | None = None
    fat_g: float | None = None
    fat_saturated_g: float | None = None
    fat_mono_g: float | None = None
    fat_poly_g: float | None = None
    carb_g: float | None = None
    sugar_g: float | None = None
    starch_g: float | None = None
    fibre_g: float | None = None
    alcohol_g: float | None = None
    sodium_mg: float | None = None
    calcium_mg: float | None = None
    iron_mg: float | None = None
    vitamin_c_mg: float | None = None
    vitamin_d_ug: float | None = None

    raw_nutrients: dict[str, Any] | None = None


class RivmItemDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    nevo_code: int | None = None

    primary_name: str
    prep_method: str | None = None
    packaging: str | None = None
    conditions: str | None = None
    raw_name: str

    nevo_naam_nl: str | None = None
    nevo_name_en: str | None = None
    nevo_productgroup_nl: str | None = None
    nevo_productgroup_en: str | None = None

    co2_kgco2eq: float | None = None
    so2_kg: float | None = None
    p_kg: float | None = None
    n_kg: float | None = None
    land_m2a: float | None = None
    water_m3: float | None = None

    # Nullable: not every RIVM row has a matching NEVO nutrition entry
    # (96.2% coverage as of P2 ingest).
    nutrition: NevoNutritionOut | None = None
