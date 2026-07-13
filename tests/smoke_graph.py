"""Smoke test — the FULL LangGraph pipeline for one lead.

research -> write -> verify (-> rewrite if rejected) -> done

Works without a Serper key: the research node then seeds findings only from
the lead's Phase-1 data (rating + website signals), which is enough to write.
Run from the project root:  python tests/smoke_graph.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdr_agent.config import DEFAULT_ICP  # noqa: E402
from sdr_agent.graph import generate_outreach  # noqa: E402
from sdr_agent.knowledge_base import KnowledgeBase  # noqa: E402
from sdr_agent.models import Lead  # noqa: E402


async def main() -> None:
    lead = Lead(
        name="Sunrise Dental Studio",
        category="Dental clinic",
        rating=4.6,
        reviews_count=98,
        website="https://sunrise-dental-example.com",
        signals=["No obvious online booking/appointment option"],
    )

    result = await generate_outreach(DEFAULT_ICP, lead)

    assert result.outreach is not None, "Graph produced no outreach"
    print("Findings collected:", len(result.findings))
    print("Attempts:", result.outreach.attempts)
    print("Approved:", result.outreach.approved)
    print("Subject:", result.outreach.subject)
    print("Body:", result.outreach.body[:300])

    kb = KnowledgeBase()
    try:
        print("Knowledge base now holds", kb.count(), "documents")
    finally:
        kb.close()

    print("\nFULL GRAPH SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
