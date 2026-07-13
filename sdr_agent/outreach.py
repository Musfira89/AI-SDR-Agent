"""Phase 2, Stage 2 — Outreach writing + verification.

Two LLM roles:

  WRITER   — drafts a personalized email + 2 follow-ups. It may ONLY use facts
             from the lead's findings. If the verifier rejected a previous
             draft, the critique is included so the rewrite can fix it.

  VERIFIER — adversarially checks the draft: does every specific claim trace
             back to a finding? Is the tone right? Returns approved/critique.

This writer->verifier->rewrite cycle is the "reflection loop" — the core
guardrail that stops the agent from inventing flattering nonsense about a
prospect (the #1 way AI outreach destroys trust).
"""

from __future__ import annotations

import json

from .models import ICP, Lead, OutreachDraft
from .scoring import _call_llm


def _findings_block(lead: Lead) -> str:
    if not lead.findings:
        return "(no findings)"
    return "\n".join(f"- [{i}] {f.text} (source: {f.source})" for i, f in enumerate(lead.findings))


async def write_outreach(icp: ICP, lead: Lead, critique: str | None = None) -> OutreachDraft:
    """Draft (or re-draft) the outreach sequence for one lead."""
    critique_block = (
        f"\nYOUR PREVIOUS DRAFT WAS REJECTED. Fix these problems:\n{critique}\n" if critique else ""
    )
    prompt = f"""You are an expert B2B sales copywriter.

We are selling: {icp.offer}
Our prospect: {lead.name} ({lead.category}) in {icp.location}.

VERIFIED FACTS about this prospect (use ONLY these — never invent anything):
{_findings_block(lead)}
{critique_block}
Write a cold outreach sequence:
1. A first email: subject + body. Max 120 words. Reference 1-2 SPECIFIC verified
   facts so it feels personally researched. Friendly, direct, no hype, one clear
   call-to-action (a short call).
2. Two short follow-ups (2-3 sentences each), polite, spaced value-adds.

Respond in JSON with exactly these keys:
{{"subject": "...", "body": "...", "followup_1": "...", "followup_2": "...",
  "cited_facts": ["the exact facts you referenced"]}}
"""
    data = json.loads(await _call_llm(prompt))
    return OutreachDraft(
        subject=data.get("subject", ""),
        body=data.get("body", ""),
        followup_1=data.get("followup_1", ""),
        followup_2=data.get("followup_2", ""),
        cited_facts=list(data.get("cited_facts", [])),
    )


async def verify_outreach(icp: ICP, lead: Lead, draft: OutreachDraft) -> tuple[bool, str]:
    """Adversarially verify a draft. Returns (approved, critique)."""
    prompt = f"""You are a strict compliance reviewer for outbound sales email.

VERIFIED FACTS about the prospect (the ONLY permitted factual claims):
{_findings_block(lead)}

DRAFT EMAIL:
Subject: {draft.subject}
Body: {draft.body}
Follow-up 1: {draft.followup_1}
Follow-up 2: {draft.followup_2}

Check, in order:
1. FABRICATION: does the draft state any specific fact about the prospect that
   is NOT supported by the verified facts above? (Generic industry statements
   are fine; invented specifics are not.)
2. LENGTH: is the first email over ~150 words?
3. TONE: is it pushy, hypey, or spammy?

Respond in JSON with exactly:
{{"approved": <true/false>, "critique": "<empty if approved; otherwise list each problem briefly>"}}
"""
    data = json.loads(await _call_llm(prompt))
    return bool(data.get("approved", False)), str(data.get("critique", ""))
