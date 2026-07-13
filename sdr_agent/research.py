"""Phase 2, Stage 1 — Deep per-lead research.

For each promising lead, a researcher runs targeted web searches (Serper) to
collect personalization angles: recent reviews, news, services, anything a
human SDR would mention to sound genuinely informed.

Every result is stored as a `Finding` with its source URL — the outreach
writer is only allowed to use facts that exist in these findings.
"""

from __future__ import annotations

import asyncio

import httpx

from .config import get_settings
from .models import ICP, Finding, Lead

SERPER_SEARCH_URL = "https://google.serper.dev/search"

MAX_RESULTS_PER_QUERY = 4


def _build_queries(lead: Lead, icp: ICP) -> list[str]:
    """Two focused queries per lead: reputation + specifics."""
    return [
        f'"{lead.name}" {icp.location} reviews',
        f'"{lead.name}" {icp.location} services news',
    ]


async def _search(client: httpx.AsyncClient, query: str) -> list[Finding]:
    """One Serper search -> findings from the organic snippets."""
    settings = get_settings()
    response = await client.post(
        SERPER_SEARCH_URL,
        headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
        json={"q": query, "num": MAX_RESULTS_PER_QUERY},
    )
    response.raise_for_status()
    data = response.json()

    findings: list[Finding] = []
    for item in data.get("organic", [])[:MAX_RESULTS_PER_QUERY]:
        snippet = item.get("snippet") or ""
        title = item.get("title") or ""
        if not snippet:
            continue
        findings.append(
            Finding(text=f"{title}: {snippet}", source=item.get("link", ""), query=query)
        )
    return findings


async def research_lead(lead: Lead, icp: ICP) -> Lead:
    """Run all research queries for one lead and attach the findings.

    Also seeds findings from data we already trust (places + website signals),
    so the writer has grounded material even if web search returns little.
    """
    settings = get_settings()

    # Seed with facts we already collected in Phase 1.
    seeded: list[Finding] = []
    if lead.rating is not None:
        seeded.append(
            Finding(
                text=f"{lead.name} has a {lead.rating} rating from {lead.reviews_count} reviews.",
                source="places_data",
            )
        )
    for signal in lead.signals:
        seeded.append(Finding(text=f"Observed on their website: {signal}", source=lead.website or "website"))

    web_findings: list[Finding] = []
    if settings.serper_api_key:
        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            results = await asyncio.gather(
                *[_search(client, query) for query in _build_queries(lead, icp)],
                return_exceptions=True,
            )
        for result in results:
            if isinstance(result, list):
                web_findings.extend(result)

    lead.findings = seeded + web_findings
    return lead
