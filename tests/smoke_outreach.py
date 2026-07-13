"""Smoke test — writer + verifier round trip with the real LLM.

Uses hand-made findings (no Serper needed). Verifies:
  1. the writer produces a valid draft grounded in the findings
  2. the verifier returns a verdict
Run from the project root:  python tests/smoke_outreach.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdr_agent.config import DEFAULT_ICP  # noqa: E402
from sdr_agent.models import Finding, Lead  # noqa: E402
from sdr_agent.outreach import verify_outreach, write_outreach  # noqa: E402


async def main() -> None:
    lead = Lead(
        name="Bright Smiles Dental",
        category="Dental clinic",
        rating=4.8,
        reviews_count=212,
        website="https://brightsmiles-example.com",
        findings=[
            Finding(text="Bright Smiles Dental has a 4.8 rating from 212 reviews.", source="places_data"),
            Finding(text="Observed on their website: No obvious online booking/appointment option", source="website"),
            Finding(text="Recent review praises Dr. Khan's gentle approach with anxious patients.", source="http://example.com/reviews"),
        ],
    )

    draft = await write_outreach(DEFAULT_ICP, lead)
    assert draft.subject and draft.body, "Writer returned an empty draft"
    print("--- WRITER OUTPUT ---")
    print("Subject:", draft.subject)
    print("Body:", draft.body[:400])
    print("Cited facts:", draft.cited_facts)

    approved, critique = await verify_outreach(DEFAULT_ICP, lead, draft)
    print("\n--- VERIFIER VERDICT ---")
    print("Approved:", approved)
    print("Critique:", critique or "(none)")
    print("\nOUTREACH SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
