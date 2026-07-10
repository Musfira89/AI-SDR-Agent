"""Stage 3 — Fit scoring with an LLM (Google Gemini).

For each enriched lead we ask Gemini to score how well it fits the ICP (0-100),
give a short reason, and flag whether it's recommended. The prompt explicitly
forbids inventing facts — the model may only reason from the data we provide.
This "grounding" rule is what keeps the output trustworthy.

The Gemini SDK call is synchronous, so we run it in a thread (asyncio.to_thread)
and bound concurrency with a semaphore to respect free-tier rate limits.
"""

from __future__ import annotations

import asyncio
import json
import re

from google import genai
from google.genai import types

from .config import get_settings
from .models import ICP, Lead

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Create the Gemini client once and reuse it."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file (see .env.example)."
            )
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _build_prompt(icp: ICP, lead: Lead) -> str:
    signals = ", ".join(icp.signals_to_look_for) or "none specified"
    lead_signals = ", ".join(lead.signals) or "none"
    excerpt = (lead.website_text or "")[:1200]
    return f"""You are a B2B sales qualification expert.

We are selling: {icp.offer}
Target industry: {icp.industry}
Target location: {icp.location}
What makes a good fit: {icp.ideal_description}
Buying signals we value: {signals}

LEAD DATA (only use these facts — do NOT invent anything):
- Name: {lead.name}
- Category: {lead.category}
- Rating: {lead.rating} ({lead.reviews_count} reviews)
- Website: {lead.website}
- Detected signals: {lead_signals}
- Website excerpt: {excerpt}

Score how well this lead fits our offer.
Return ONLY JSON with exactly these keys:
{{"fit_score": <int 0-100>, "reason": "<1-2 sentences grounded only in the data above>", "recommended": <true if fit_score >= 60 else false>}}
"""


def _extract_json(text: str) -> dict:
    """Parse JSON from the model output, tolerating code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text).rstrip("`").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _score_sync(icp: ICP, lead: Lead) -> Lead:
    settings = get_settings()
    client = _get_client()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=_build_prompt(icp, lead),
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    data = _extract_json(response.text or "")
    lead.fit_score = int(data.get("fit_score", 0))
    lead.score_reason = data.get("reason")
    lead.recommended = bool(data.get("recommended", (lead.fit_score or 0) >= 60))
    return lead


async def score_lead(icp: ICP, lead: Lead) -> Lead:
    """Score one lead. On failure, records the error instead of crashing."""
    try:
        return await asyncio.to_thread(_score_sync, icp, lead)
    except Exception as exc:  # noqa: BLE001 — we want the pipeline to survive
        lead.fit_score = None
        lead.score_reason = f"scoring_failed: {exc}"
        lead.recommended = False
        return lead


async def score_leads(icp: ICP, leads: list[Lead]) -> list[Lead]:
    """Score all leads concurrently, bounded by a semaphore."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.scoring_concurrency)

    async def _task(lead: Lead) -> Lead:
        async with semaphore:
            return await score_lead(icp, lead)

    return await asyncio.gather(*[_task(lead) for lead in leads])
