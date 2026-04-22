from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.reference_session import get_reference_session
from app.models.reference import NevoNutrition, RivmItem
from app.schemas.ingredient import (
    IngredientGroup,
    IngredientSearchResponse,
    IngredientVariant,
    NevoNutritionOut,
    RivmItemDetail,
)
from app.services.matching.search import search_ingredients, variant_label

router = APIRouter(prefix="/api", tags=["ingredients"])


@router.get("/ingredients", response_model=IngredientSearchResponse)
def list_ingredients(
    mode: str = Query(..., pattern="^(meal|procurement)$"),
    q: str = Query(..., min_length=1, description="Free-text search term"),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_reference_session),
) -> IngredientSearchResponse:
    scored = search_ingredients(session, mode=mode, query=q, limit=limit)

    results: list[IngredientGroup] = []
    for s in scored:
        g = s.group
        variants = [
            IngredientVariant(
                rivm_item_id=r.id,
                label=variant_label(r),
                stage=r.stage,
                prep_method=r.prep_method,
                packaging=r.packaging,
                conditions=r.conditions,
                co2_kgco2eq=r.co2_kgco2eq,
                so2_kg=r.so2_kg,
                p_kg=r.p_kg,
                n_kg=r.n_kg,
                land_m2a=r.land_m2a,
                water_m3=r.water_m3,
            )
            for r in g.rows
        ]
        results.append(
            IngredientGroup(
                primary_name=g.primary_name,
                nevo_code=g.nevo_code,
                nevo_name_nl=g.nevo_naam_nl,
                nevo_name_en=g.nevo_name_en,
                nevo_productgroup_nl=g.nevo_productgroup_nl,
                nevo_productgroup_en=g.nevo_productgroup_en,
                score=s.score,
                variants=variants,
            )
        )

    return IngredientSearchResponse(mode=mode, query=q, results=results)


@router.get("/rivm_item/{item_id}", response_model=RivmItemDetail)
def get_rivm_item(
    item_id: int,
    session: Session = Depends(get_reference_session),
) -> RivmItemDetail:
    row = session.get(RivmItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"rivm_item {item_id} not found")

    detail = RivmItemDetail.model_validate(row)
    if row.nevo_code is not None:
        nutrition = session.get(NevoNutrition, row.nevo_code)
        if nutrition is not None:
            detail.nutrition = NevoNutritionOut.model_validate(nutrition)
    return detail
