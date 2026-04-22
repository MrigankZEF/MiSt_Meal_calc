from fastapi.testclient import TestClient


def test_meal_mode_returns_grouped_variants(client: TestClient) -> None:
    r = client.get("/api/ingredients", params={"mode": "meal", "q": "sweet potato"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "meal"
    assert body["query"] == "sweet potato"
    assert len(body["results"]) >= 1

    top = body["results"][0]
    assert top["primary_name"] == "Sweet potatoes"
    assert top["nevo_code"] == 100

    labels = [v["label"] for v in top["variants"]]
    # retail "supermarket" plus two consumption prep methods. No distribution.
    assert set(labels) == {"supermarket", "boiling", "pan frying"}
    assert all(v["stage"] in {"retail", "consumption"} for v in top["variants"])
    # Retail sorts before consumption.
    assert labels[0] == "supermarket"


def test_procurement_mode_returns_distribution_only(client: TestClient) -> None:
    r = client.get(
        "/api/ingredients", params={"mode": "procurement", "q": "sweet potato"}
    )
    assert r.status_code == 200
    body = r.json()
    top = body["results"][0]
    assert top["nevo_code"] == 100
    assert len(top["variants"]) == 1
    assert top["variants"][0]["stage"] == "distribution"
    assert top["variants"][0]["label"] == "distribution"


def test_search_ranks_best_match_first(client: TestClient) -> None:
    r = client.get("/api/ingredients", params={"mode": "meal", "q": "bell pepper"})
    assert r.status_code == 200
    body = r.json()
    # Bell pepper should rank first; other fuzzy matches may follow but lower.
    assert body["results"][0]["primary_name"] == "Bell pepper"
    if len(body["results"]) > 1:
        assert body["results"][0]["score"] >= body["results"][1]["score"]


def test_unknown_mode_rejected(client: TestClient) -> None:
    r = client.get("/api/ingredients", params={"mode": "bogus", "q": "potato"})
    assert r.status_code == 422


def test_empty_query_rejected(client: TestClient) -> None:
    r = client.get("/api/ingredients", params={"mode": "meal", "q": ""})
    assert r.status_code == 422


def test_get_rivm_item_detail(client: TestClient) -> None:
    search = client.get(
        "/api/ingredients", params={"mode": "meal", "q": "sweet potato"}
    ).json()
    item_id = search["results"][0]["variants"][0]["rivm_item_id"]

    r = client.get(f"/api/rivm_item/{item_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == item_id
    assert body["primary_name"] == "Sweet potatoes"
    assert body["raw_name"].startswith("Sweet potatoes |")


def test_get_rivm_item_not_found(client: TestClient) -> None:
    r = client.get("/api/rivm_item/99999")
    assert r.status_code == 404


# ---- scoring: exact/stem matches must beat processed-word variants ----


def test_plain_potato_outranks_potato_starch(client: TestClient) -> None:
    """Query 'potato' must rank 'Potato starch' (processed) below
    'Sweet potatoes' (plain food with 'potato' in stems)."""
    r = client.get("/api/ingredients", params={"mode": "meal", "q": "potato"})
    body = r.json()
    names = [g["primary_name"] for g in body["results"]]
    # Both should appear...
    assert "Sweet potatoes" in names
    assert "Potato starch" in names
    # ...but plain/unprocessed forms rank ahead of 'Potato starch'.
    assert names.index("Sweet potatoes") < names.index("Potato starch")


def test_plain_tomato_outranks_tomato_sauce(client: TestClient) -> None:
    r = client.get("/api/ingredients", params={"mode": "meal", "q": "tomato"})
    body = r.json()
    names = [g["primary_name"] for g in body["results"]]
    assert names[0] == "Tomato"  # exact match → score 120
    assert "Tomato sauce" in names
    assert names.index("Tomato") < names.index("Tomato sauce")


def test_stem_match_finds_plural(client: TestClient) -> None:
    """Query 'potatoes' should match 'Potato' and 'Sweet potatoes' via stems."""
    r = client.get("/api/ingredients", params={"mode": "meal", "q": "potatoes"})
    body = r.json()
    names = [g["primary_name"] for g in body["results"]]
    assert "Sweet potatoes" in names
    assert "Potato" in names


# ---- nutrition join on detail endpoint ----


def _find_item_id(client: TestClient, mode: str, primary_name: str) -> int:
    """Look up a rivm_item_id by primary_name via search."""
    body = client.get(
        "/api/ingredients", params={"mode": mode, "q": primary_name}
    ).json()
    for g in body["results"]:
        if g["primary_name"] == primary_name:
            return g["variants"][0]["rivm_item_id"]
    raise AssertionError(f"no group with primary_name={primary_name!r}")


def test_detail_includes_nutrition_when_nevo_matched(client: TestClient) -> None:
    """nevo_code=200 (Potato) has a seeded NevoNutrition row."""
    item_id = _find_item_id(client, "procurement", "Potato")
    r = client.get(f"/api/rivm_item/{item_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["nevo_code"] == 200
    assert body["nutrition"] is not None
    n = body["nutrition"]
    assert n["nevo_code"] == 200
    assert n["english_name"] == "Potatoes raw"
    assert n["kcal"] == 77.0
    assert n["protein_g"] == 2.0
    # Lossless raw dict is surfaced verbatim
    assert n["raw_nutrients"] == {"ENERCC (kcal)": 77.0, "NEVO-code": 200}


def test_detail_nutrition_null_when_no_nevo_match(client: TestClient) -> None:
    """nevo_code=100 (Sweet potatoes) has no NevoNutrition row in the fixture —
    detail endpoint must still return 200 with nutrition=None."""
    item_id = _find_item_id(client, "meal", "Sweet potatoes")
    r = client.get(f"/api/rivm_item/{item_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["nevo_code"] == 100
    assert body["nutrition"] is None
