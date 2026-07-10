"""Stage 1 — Lead discovery.

We use Serper.dev's "places" endpoint (a Google Maps-style search) to find real
local businesses matching the ICP. It returns structured data (name, address,
phone, website, rating, reviews) for free — a great baseline before enrichment.
"""

from __future__ import annotations

import httpx

from .config import get_settings
from .models import ICP, Lead

SERPER_PLACES_URL = "https://google.serper.dev/places"


async def discover_leads(icp: ICP, limit: int = 20) -> list[Lead]:
    """Find up to `limit` businesses matching the ICP.

    Raises RuntimeError if the Serper API key is missing.
    """
    settings = get_settings()
    if not settings.serper_api_key:
        raise RuntimeError(
            "SERPER_API_KEY is not set. Add it to your .env file (see .env.example)."
        )

    query = f"{icp.industry} in {icp.location}"
    headers = {
        "X-API-KEY": settings.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {"q": query}

    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        response = await client.post(SERPER_PLACES_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    places = data.get("places", [])[:limit]

    leads: list[Lead] = []
    for place in places:
        leads.append(
            Lead(
                name=place.get("title") or "Unknown business",
                address=place.get("address"),
                phone=place.get("phoneNumber"),
                website=place.get("website"),
                rating=place.get("rating"),
                reviews_count=place.get("ratingCount"),
                category=place.get("category"),
            )
        )
    return leads
