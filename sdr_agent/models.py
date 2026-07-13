"""Pydantic data models — the typed "shapes" that flow through the pipeline.

There are two models:
  - ICP   : the INPUT — who we are targeting and what we sell.
  - Lead  : one prospect, filled in progressively as it moves through the
            pipeline (discovery -> enrichment -> scoring).

Using Pydantic gives us validation for free and makes every stage's data
predictable, which is exactly what real agent systems need.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ICP(BaseModel):
    """Ideal Customer Profile + the offer we are pitching.

    Everything here is configuration — change these fields to re-target the
    whole agent at a different vertical (salons, HVAC, law firms, etc.).
    """

    industry: str = Field(..., description="e.g. 'dental clinics'")
    location: str = Field(..., description="e.g. 'Austin, Texas'")
    offer: str = Field(..., description="What we are selling to this business")
    ideal_description: str = Field(
        ...,
        description="Free-text description of what makes a business a good fit",
    )
    signals_to_look_for: list[str] = Field(
        default_factory=list,
        description="Buying signals that raise the fit score, e.g. 'no online booking'",
    )


class Finding(BaseModel):
    """One verified piece of research about a lead (Phase 2).

    Every fact the outreach writer uses must trace back to one of these —
    that traceability is our anti-hallucination guardrail.
    """

    text: str
    source: str = ""     # URL or "places_data"
    query: str = ""      # the search query that surfaced it


class OutreachDraft(BaseModel):
    """A personalized outreach sequence for one lead (Phase 2)."""

    subject: str
    body: str
    followup_1: str = ""
    followup_2: str = ""
    cited_facts: list[str] = Field(default_factory=list)
    approved: bool = False       # did the verifier approve it?
    critique: str | None = None  # verifier feedback (used for the rewrite loop)
    attempts: int = 1


class Lead(BaseModel):
    """A single prospect. Fields are filled in across the three pipeline stages."""

    # --- Stage 1: discovery (from the places/search API) ---
    name: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    category: str | None = None

    # --- Stage 2: enrichment (from scraping the website) ---
    email: str | None = None
    socials: dict[str, str] = Field(default_factory=dict)
    website_text: str | None = None          # trimmed visible text for the scorer
    signals: list[str] = Field(default_factory=list)  # detected gaps/opportunities
    enrichment_status: str = "pending"       # pending | ok | no_website | failed

    # --- Stage 3: scoring (from the LLM) ---
    fit_score: int | None = None             # 0-100
    score_reason: str | None = None
    recommended: bool | None = None

    # --- Memory ---
    previously_seen: bool = False            # seen in an earlier run?

    # --- Phase 2: research + outreach ---
    findings: list[Finding] = Field(default_factory=list)
    outreach: OutreachDraft | None = None
