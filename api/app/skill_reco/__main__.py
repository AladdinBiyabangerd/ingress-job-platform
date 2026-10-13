"""Interactive simulation walkthrough.

Run from ``api/``::

    .venv/bin/python -m app.skill_reco
"""

from __future__ import annotations

from app.skill_reco.catalog import SkillCatalog
from app.skill_reco.engine import HybridRecommender, Recommendation
from app.skill_reco.session import UserSession


def _print_list(title: str, rows: list[Recommendation]) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    if not rows:
        print("  (empty)")
        return
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.bucket] = counts.get(row.bucket, 0) + 1
    print(
        "bucket mix:",
        ", ".join(f"{k}={v}" for k, v in sorted(counts.items())),
        f"(n={len(rows)})",
    )
    print(f"{'#':>2}  {'skill':<22} {'category':<18} {'bucket':<12} {'sim':>6} {'score':>6}")
    print("-" * 72)
    for i, row in enumerate(rows, start=1):
        print(
            f"{i:>2}  {row.name:<22} {row.category:<18} {row.bucket:<12} "
            f"{row.similarity:>6.3f} {row.score:>6.3f}"
        )


def _print_session(session: UserSession, catalog: SkillCatalog) -> None:
    print()
    print("session clicks (oldest → newest) with decay weights:")
    for skill_id, weight in session.debug_weights():
        skill = catalog.get(skill_id)
        name = skill.name if skill else str(skill_id)
        print(f"  w={weight:.3f}  {name}")
    vec = session.session_vector()
    if vec:
        pretty = ", ".join(f"{x:.3f}" for x in vec)
        print(f"session vector (L2): [{pretty}]")
        print(
            "axes: design | code | product | data | marketing"
        )


def main() -> None:
    catalog = SkillCatalog()
    engine = HybridRecommender(catalog)
    session = UserSession(decay=0.7, max_history=8)

    # Step 1 — cold start
    cold = engine.get_recommendations(session, top_n=10)
    _print_list("Step 1 — Cold start (no history → global popularity)", cold)

    # Step 2 — first choice: Figma
    figma = catalog.get_by_name("Figma")
    assert figma is not None
    session.click(figma)
    _print_session(session, catalog)
    after_figma = engine.get_recommendations(session, top_n=10)
    _print_list(
        "Step 2 — After click: Figma (UI/UX) — expect design exploit + web/product adjacent",
        after_figma,
    )

    # Step 3 — shift toward coding via HTML/CSS
    html = catalog.get_by_name("HTML/CSS")
    assert html is not None
    session.click(html)
    _print_session(session, catalog)
    after_html = engine.get_recommendations(session, top_n=10)
    _print_list(
        "Step 3 — After click: HTML/CSS — session at Design ∩ Coding intersection",
        after_html,
    )

    print()
    print("Scaling notes")
    print("-" * 72)
    print(
        "* Swap SkillCatalog for a DB/API loader; keep the same Skill.embedding shape.\n"
        "* Replace brute-force cosine loops with ANN:\n"
        "    Pinecone / ChromaDB / pgvector.query(vector=session_vec, top_k=200)\n"
        "  then run the 60/25/15 partition on that candidate set only.\n"
        "* Train real embeddings (skill co-occurrence Word2Vec, SBERT, or graph\n"
        "  embeddings) offline; refresh vectors in the vector DB on a schedule.\n"
        "* Persist UserSession.clicked_ids per user in Redis with TTL; rebuild the\n"
        "  session vector on each click (O(history) and history ≤ 8)."
    )


if __name__ == "__main__":
    main()
