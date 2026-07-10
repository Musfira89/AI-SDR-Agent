"""Stage 2 — Enrichment.

For each discovered lead we visit its website and extract extra signals:
  - a contact email
  - social media links
  - a trimmed slice of the page text (used later by the scorer)
  - simple "opportunity" signals (e.g. no online booking found)

Everything runs concurrently with an asyncio semaphore so we scrape many sites
in parallel without hammering the network — this is where async pays off.
"""

from __future__ import annotations

import asyncio
import re

import httpx
from bs4 import BeautifulSoup

from .config import get_settings
from .models import ICP, Lead

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Social platforms we try to detect from link hrefs.
SOCIAL_DOMAINS = {
    "facebook": "facebook.com",
    "instagram": "instagram.com",
    "linkedin": "linkedin.com",
    "twitter": "twitter.com",
    "x": "x.com",
    "youtube": "youtube.com",
}

# Keywords that suggest the site already offers online booking.
BOOKING_KEYWORDS = ("book", "appointment", "schedule", "booking")


async def _fetch_html(client: httpx.AsyncClient, url: str) -> str:
    """Fetch a URL, adding https:// if the scheme is missing."""
    if not url.startswith("http"):
        url = "https://" + url
    response = await client.get(url, follow_redirects=True)
    response.raise_for_status()
    return response.text


async def enrich_lead(client: httpx.AsyncClient, lead: Lead) -> Lead:
    """Enrich a single lead by scraping its website. Never raises — on failure
    it just records a status so the pipeline keeps going."""
    if not lead.website:
        lead.enrichment_status = "no_website"
        lead.signals.append("No website found")
        return lead

    try:
        html = await _fetch_html(client, lead.website)
    except Exception:
        lead.enrichment_status = "failed"
        return lead

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    # Contact email
    match = EMAIL_RE.search(html)
    if match:
        lead.email = match.group(0)

    # Social links
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].lower()
        for name, domain in SOCIAL_DOMAINS.items():
            if domain in href and name not in lead.socials:
                lead.socials[name] = anchor["href"]

    # Trim page text for the scorer (keeps prompts small and cheap)
    lead.website_text = text[:2000]

    # Simple opportunity signals
    lowered = text.lower()
    if not any(keyword in lowered for keyword in BOOKING_KEYWORDS):
        lead.signals.append("No obvious online booking/appointment option")
    if not lead.email:
        lead.signals.append("No email visible on site")

    lead.enrichment_status = "ok"
    return lead


async def enrich_leads(leads: list[Lead], icp: ICP) -> list[Lead]:
    """Enrich all leads concurrently, bounded by a semaphore."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.enrichment_concurrency)

    async with httpx.AsyncClient(
        timeout=settings.request_timeout,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SDR-Agent/0.1)"},
    ) as client:

        async def _task(lead: Lead) -> Lead:
            async with semaphore:
                return await enrich_lead(client, lead)

        return await asyncio.gather(*[_task(lead) for lead in leads])
