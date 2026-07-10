"""The Phase 1 pipeline — ties the three stages together.

    discover  ->  enrich  ->  score  ->  sort by fit

An optional `on_progress` callback lets the UI show live status messages.
"""

from __future__ import annotations

from collections.abc import Callable

from .discovery import discover_leads
from .enrichment import enrich_leads
from .models import ICP, Lead
from .scoring import score_leads


async def run_pipeline(
    icp: ICP,
    limit: int = 20,
    on_progress: Callable[[str], None] | None = None,
) -> list[Lead]:
    """Run discovery -> enrichment -> scoring and return leads sorted by fit."""

    def notify(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    notify("🔍 Discovering leads...")
    leads = await discover_leads(icp, limit=limit)
    notify(f"✅ Found {len(leads)} leads. Enriching websites...")

    if not leads:
        return leads

    leads = await enrich_leads(leads, icp)
    notify("📇 Enrichment done. Scoring fit with the LLM...")

    leads = await score_leads(icp, leads)
    notify("🎯 Scoring complete.")

    # Highest fit first; unscored (None) leads sink to the bottom.
    leads.sort(key=lambda lead: (lead.fit_score is not None, lead.fit_score or 0), reverse=True)
    return leads
