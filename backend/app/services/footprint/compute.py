"""Compute aggregate environmental totals for a list of RIVM items.

Used at meal/procurement save time so the totals are stored in the user DB
and can be aggregated cheaply for the dashboard without re-fetching all items.

The reference DB session is the *synchronous* SQLAlchemy Session from
``app.db.reference_session``.  FastAPI runs sync dependencies in a thread
pool so this is safe to inject into async route handlers.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from app.models.reference import RivmItem


def _to_kg(amount: float, unit: str) -> float:
    """Convert amount + unit to kilograms.

    Mirrors the frontend ``toKg`` utility in ``src/utils/units.ts``.
    Density = 1.0 for liquids (matching v1 behaviour).
    Piece weight = 100 g fallback (same as v1).
    """
    u = unit.lower()
    if u in ("g", "ml"):
        return amount / 1000.0
    if u in ("kg", "l"):
        return amount
    if u == "piece":
        return amount * 0.1   # 100 g default
    return amount / 1000.0    # unknown → treat as grams


def compute_totals(
    ref_session: Session,
    items: list[tuple[int, float, str]],  # (rivm_item_id, amount, unit)
) -> dict[str, float]:
    """Return summed environmental totals for a list of (id, amount, unit) tuples.

    Returns a dict with keys:
        co2_kg, water_m3, land_m2a, so2_kg, p_kg, n_kg
    All values are 0.0 when the list is empty or no matching RIVM rows exist.
    """
    zero: dict[str, float] = {
        "co2_kg": 0.0, "water_m3": 0.0, "land_m2a": 0.0,
        "so2_kg": 0.0, "p_kg": 0.0,     "n_kg": 0.0,
    }
    if not items:
        return zero

    ids = list({i[0] for i in items})
    rows = ref_session.query(RivmItem).filter(RivmItem.id.in_(ids)).all()
    rivm_map: dict[int, RivmItem] = {r.id: r for r in rows}

    totals = dict(zero)
    for rivm_id, amount, unit in items:
        r = rivm_map.get(rivm_id)
        if r is None:
            continue
        kg = _to_kg(amount, unit)
        totals["co2_kg"]   += kg * (r.co2_kgco2eq or 0.0)
        totals["water_m3"] += kg * (r.water_m3    or 0.0)
        totals["land_m2a"] += kg * (r.land_m2a    or 0.0)
        totals["so2_kg"]   += kg * (r.so2_kg      or 0.0)
        totals["p_kg"]     += kg * (r.p_kg        or 0.0)
        totals["n_kg"]     += kg * (r.n_kg        or 0.0)
    return totals


async def compute_totals_async(
    items: list[tuple[int, float, str]],
) -> dict[str, float]:
    """Async-safe wrapper: runs compute_totals in a thread pool with its own session.

    Avoids any cross-thread SQLAlchemy session issues when called from async
    route handlers.  A fresh Session is created inside the worker thread so
    the connection is always made from the thread that uses it.
    """
    from app.db.reference_session import ReferenceSession   # local import avoids circulars

    def _run() -> dict[str, float]:
        with ReferenceSession() as session:
            return compute_totals(session, items)

    return await asyncio.to_thread(_run)
