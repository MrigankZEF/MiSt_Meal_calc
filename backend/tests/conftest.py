"""Shared pytest fixtures.

Each test gets an in-memory SQLite reference DB seeded with a handful of
RivmItem rows covering all three stages. The FastAPI dependency
`get_reference_session` is overridden to use this DB so tests never touch
the committed `data/reference.db`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.reference_session import get_reference_session
from app.main import app
from app.models.reference import NevoNutrition, RivmItem


def _seed(session: Session) -> None:
    session.add_all(
        [
            # Sweet potato — appears in all three stages.
            RivmItem(
                stage="distribution",
                nevo_code=100,
                primary_name="Sweet potatoes",
                prep_method=None,
                packaging="Ambient",
                conditions=None,
                raw_name="Sweet potatoes | Ambient | 500 g | at distribution/NL Economic",
                nevo_naam_nl="Zoete aardappel",
                nevo_name_en="Sweet potatoes",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=0.5,
                so2_kg=0.01,
                p_kg=0.001,
                n_kg=0.002,
                land_m2a=0.3,
                water_m3=0.04,
            ),
            RivmItem(
                stage="retail",
                nevo_code=100,
                primary_name="Sweet potatoes",
                prep_method="supermarket",
                packaging="Ambient",
                conditions=None,
                raw_name="Sweet potatoes | Ambient | 500 g | at supermarket/NL Economic",
                nevo_naam_nl="Zoete aardappel",
                nevo_name_en="Sweet potatoes",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=0.7,
            ),
            RivmItem(
                stage="consumption",
                nevo_code=100,
                primary_name="Sweet potatoes",
                prep_method="boiling",
                packaging="Ambient",
                conditions=None,
                raw_name="Sweet potatoes | Ambient | 500 g | Boiling | consumed/NL Economic",
                nevo_naam_nl="Zoete aardappel",
                nevo_name_en="Sweet potatoes",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=0.9,
            ),
            RivmItem(
                stage="consumption",
                nevo_code=100,
                primary_name="Sweet potatoes",
                prep_method="pan frying",
                packaging="Ambient",
                conditions=None,
                raw_name="Sweet potatoes | Ambient | 500 g | Pan frying | consumed/NL Economic",
                nevo_naam_nl="Zoete aardappel",
                nevo_name_en="Sweet potatoes",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=1.1,
            ),
            # Plain potato — distribution + retail only, different NEVO.
            RivmItem(
                stage="distribution",
                nevo_code=200,
                primary_name="Potato",
                prep_method=None,
                packaging="Ambient",
                conditions=None,
                raw_name="Potato | Ambient | 1 kg | at distribution/NL Economic",
                nevo_naam_nl="Aardappel",
                nevo_name_en="Potato",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=0.3,
            ),
            RivmItem(
                stage="retail",
                nevo_code=200,
                primary_name="Potato",
                prep_method="supermarket",
                packaging="Ambient",
                conditions=None,
                raw_name="Potato | Ambient | 1 kg | at supermarket/NL Economic",
                nevo_naam_nl="Aardappel",
                nevo_name_en="Potato",
                nevo_productgroup_nl="Aardappelen",
                nevo_productgroup_en="Potatoes",
                co2_kgco2eq=0.35,
            ),
            # Unrelated row to make sure search doesn't return everything.
            RivmItem(
                stage="retail",
                nevo_code=300,
                primary_name="Bell pepper",
                prep_method="supermarket",
                packaging="Ambient",
                conditions=None,
                raw_name="Bell pepper | Ambient | 500 g | at supermarket/NL Economic",
                nevo_naam_nl="Paprika",
                nevo_name_en="Bell pepper",
                nevo_productgroup_nl="Groenten",
                nevo_productgroup_en="Vegetables",
                co2_kgco2eq=1.8,
            ),
            # Distinct processed product sharing the "potato" token — must
            # rank BELOW plain potato for query "potato" because 'starch'
            # is a processed-word modifier.
            RivmItem(
                stage="retail",
                nevo_code=400,
                primary_name="Potato starch",
                prep_method="supermarket",
                packaging="Ambient",
                conditions=None,
                raw_name="Potato starch | Ambient | 500 g | at supermarket/NL Economic",
                nevo_naam_nl="Aardappelzetmeel",
                nevo_name_en="Potato starch",
                nevo_productgroup_nl="Aardappelproducten",
                nevo_productgroup_en="Potato products",
                co2_kgco2eq=1.2,
            ),
            # Plain tomato + a sauce variant (processed) to validate the
            # modifier penalty in the tomato axis.
            RivmItem(
                stage="retail",
                nevo_code=500,
                primary_name="Tomato",
                prep_method="supermarket",
                packaging="Ambient",
                conditions=None,
                raw_name="Tomato | Ambient | 500 g | at supermarket/NL Economic",
                nevo_naam_nl="Tomaat",
                nevo_name_en="Tomato",
                nevo_productgroup_nl="Groenten",
                nevo_productgroup_en="Vegetables",
                co2_kgco2eq=0.6,
            ),
            # Nutrition rows for a couple of NEVO codes so we can test
            # the /api/rivm_item/{id} nutrition join. nevo_code=200 (Potato)
            # gets one; nevo_code=100 (Sweet potatoes) deliberately does NOT
            # so we can test the null-nutrition case.
            NevoNutrition(
                nevo_code=200,
                dutch_name="Aardappelen rauw",
                english_name="Potatoes raw",
                food_group_nl="Aardappelen en knolgewassen",
                food_group_en="Potatoes and tubers",
                quantity="per 100g",
                kj=325.0,
                kcal=77.0,
                water_g=80.0,
                protein_g=2.0,
                fat_g=0.1,
                carb_g=17.0,
                fibre_g=2.2,
                raw_nutrients={"ENERCC (kcal)": 77.0, "NEVO-code": 200},
            ),
            RivmItem(
                stage="retail",
                nevo_code=501,
                primary_name="Tomato sauce",
                prep_method="supermarket",
                packaging="Jar",
                conditions=None,
                raw_name="Tomato sauce | Jar | 500 g | at supermarket/NL Economic",
                nevo_naam_nl="Tomatensaus",
                nevo_name_en="Tomato sauce",
                nevo_productgroup_nl="Sauzen",
                nevo_productgroup_en="Sauces",
                co2_kgco2eq=1.4,
            ),
        ]
    )
    session.commit()


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    with TestingSession() as s:
        _seed(s)

    def _override() -> Iterator[Session]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_reference_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
