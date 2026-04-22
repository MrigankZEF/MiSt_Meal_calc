"""Eyeball the scorer against the live reference.db.

Runs a set of common queries across both modes and prints the top-N hits
so we can sanity-check ranking. Not a pytest — just a debug harness.

    cd backend && .venv/bin/python scripts/validate_search.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.reference_session import ReferenceSession
from app.services.matching.search import search_ingredients, variant_label

QUERIES = ["potato", "tomato", "chicken", "onion", "oil", "cheese", "aardappel"]
MODES = ["meal", "procurement"]


def main() -> None:
    with ReferenceSession() as session:
        for mode in MODES:
            print(f"\n===== mode={mode} " + "=" * 40)
            for q in QUERIES:
                results = search_ingredients(session, mode=mode, query=q, limit=5)
                print(f"\n  q={q!r}   ({len(results)} hits)")
                for s in results:
                    g = s.group
                    variants = [variant_label(r) for r in g.rows]
                    print(
                        f"    {s.score:6.1f}  {g.primary_name:<40s}"
                        f"  nevo={g.nevo_code}  variants={variants}"
                    )


if __name__ == "__main__":
    main()
