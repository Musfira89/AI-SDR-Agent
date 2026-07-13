"""Stage 3 — Fit scoring with an LLM (Groq, llama-3.3-70b).

For each enriched lead we ask the model to score how well it fits the ICP
(0-100), give a short reason, and flag whether it's recommended. The prompt
explicitly forbids inventing facts — the model may only reason from the data
we provide. This "grounding" rule is what keeps the output trustworthy.

Groq's SDK has a native async client (AsyncGroq), and we use its JSON mode
(`response_format={"type": "json_object"}`) so the reply is always parseable.
Calls are wrapped in retry-with-backoff to survive free-tier rate limits.
"""

from __future__ import annotations

import asyncio
import json

from groq import AsyncGroq

from .config import get_settings
from .models import ICP, Lead
from .utils import async_retry

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """Create the Groq client once and reuse it."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your .env file (see .env.example)."
            )
        _client = AsyncGroq(api_key=settings.groq_api_key)
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
Respond in JSON with exactly these keys:
{{"fit_score": <int 0-100>, "reason": "<1-2 sentences grounded only in the data above>", "recommended": <true if fit_score >= 60 else false>}}
"""


@async_retry(max_attempts=3, base_delay=2.0)
async def _call_llm(prompt: str) -> str:
    """One LLM call with JSON mode. Retried with backoff on failure."""
    settings = get_settings()
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.groq_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


async def score_lead(icp: ICP, lead: Lead) -> Lead:
    """Score one lead. On failure, records the error instead of crashing."""
    try:
        data = json.loads(await _call_llm(_build_prompt(icp, lead)))
        lead.fit_score = int(data.get("fit_score", 0))
        lead.score_reason = data.get("reason")
        lead.recommended = bool(data.get("recommended", lead.fit_score >= 60))
    except Exception as exc:  # noqa: BLE001 — we want the pipeline to survive
        lead.fit_score = None
        lead.score_reason = f"scoring_failed: {exc}"
        lead.recommended = False
    return lead


async def score_leads(icp: ICP, leads: list[Lead]) -> list[Lead]:
    """Score all leads concurrently, bounded by a semaphore (rate-limit safety)."""
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.scoring_concurrency)

    async def _task(lead: Lead) -> Lead:
        async with semaphore:
            return await score_lead(icp, lead)

    return await asyncio.gather(*[_task(lead) for lead in leads])
