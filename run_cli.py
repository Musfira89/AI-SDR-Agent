"""Command-line runner — handy for testing the pipeline without the UI.

Run with:  python run_cli.py
Edit the ICP below or just use the demo default.
"""

from __future__ import annotations

import asyncio
import sys

# Windows consoles often default to a legacy encoding (cp1252) that cannot
# print unicode; force UTF-8 so output never crashes the run.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from sdr_agent.config import DEFAULT_ICP
from sdr_agent.pipeline import run_pipeline
from sdr_agent.storage import export_to_csv


async def main() -> None:
    icp = DEFAULT_ICP  # swap for your own ICP(...) here
    leads = await run_pipeline(icp, limit=10, on_progress=print)

    print("\n=== RESULTS (sorted by fit) ===")
    for lead in leads:
        score = lead.fit_score if lead.fit_score is not None else "-"
        print(f"[{score:>3}] {lead.name}  ({lead.website or 'no site'})")
        if lead.score_reason:
            print(f"      reason: {lead.score_reason}")

    path = export_to_csv(leads, "leads.csv")
    print(f"\nSaved {len(leads)} leads to {path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
