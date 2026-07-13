"""The Phase 1 pipeline — ties all stages together.

    discover -> dedupe -> memory check -> enrich -> score -> sort -> remember

An optional `on_progress` callback lets the UI show live status messages.
"""

from __future__ import annotations

from collections.abc import Callable

from .discovery import discover_leads
from .enrichment import enrich_leads
from .memory import LeadMemory, dedupe_batch
from .models import ICP, Lead
from .scoring import score_leads


async def run_pipeline(
    icp: ICP,
    limit: int = 20,
    skip_seen: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> list[Lead]:
    """Run the full pipeline and return leads sorted by fit (best first).

    skip_seen: if True, leads processed in earlier runs are dropped before
    enrichment/scoring (saves tokens and avoids double-contacting). If False,
    they are kept but flagged `previously_seen=True`.
    """

    def notify(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    notify("Discovering leads...")
    leads = await discover_leads(icp, limit=limit)
    notify(f"Found {len(leads)} leads. Checking duplicates & memory...")

    # Remove near-duplicates within this batch.
    leads = dedupe_batch(leads)

    # Flag / skip leads we've already processed in earlier runs.
    memory = LeadMemory()
    try:
        for lead in leads:
            lead.previously_seen = memory.is_seen(lead)

        if skip_seen:
            fresh = [lead for lead in leads if not lead.previously_seen]
            skipped = len(leads) - len(fresh)
            if skipped:
                notify(f"Skipped {skipped} previously-seen lead(s).")
            leads = fresh

        if not leads:
            notify("No new leads to process.")
            return leads

        notify(f"Enriching {len(leads)} website(s)...")
        leads = await enrich_leads(leads, icp)

        notify("Scoring fit with the LLM...")
        leads = await score_leads(icp, leads)

        # Remember every lead we fully processed.
        for lead in leads:
            memory.mark_seen(lead)
    finally:
        memory.close()

    notify("Scoring complete.")

    # Highest fit first; unscored (None) leads sink to the bottom.
    leads.sort(key=lambda lead: (lead.fit_score is not None, lead.fit_score or 0), reverse=True)
    return leads
