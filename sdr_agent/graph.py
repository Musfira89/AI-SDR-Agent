"""Phase 2 orchestration — a LangGraph state machine per lead.

The graph (drawn before coded — Rule 01):

    ┌──────────┐     ┌───────┐     ┌────────┐   approved / max tries
    │ research │ --> │ write │ --> │ verify │ ------------------------> END
    └──────────┘     └───────┘     └────────┘
                         ▲              │ rejected (with critique)
                         └──────────────┘

Why a graph instead of straight-line code? The verify->write cycle is a LOOP
with state (attempts, critique) and an exit condition. That's exactly what
state machines model well — and if this later needs checkpointing or human
approval gates, LangGraph gives them without a rewrite.
"""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .knowledge_base import KnowledgeBase
from .models import ICP, Lead, OutreachDraft
from .outreach import verify_outreach, write_outreach
from .research import research_lead

MAX_WRITE_ATTEMPTS = 2


class OutreachState(TypedDict):
    """Everything the graph knows about one lead's outreach job."""

    icp: ICP
    lead: Lead
    draft: OutreachDraft | None
    critique: str | None
    attempts: int
    approved: bool


# ---------- nodes ----------

async def research_node(state: OutreachState) -> dict:
    """Gather findings for the lead and archive them in the knowledge base."""
    lead = await research_lead(state["lead"], state["icp"])

    kb = KnowledgeBase()
    try:
        for finding in lead.findings:
            kb.add(
                text=finding.text,
                source=finding.source,
                lead=lead.name,
                location=state["icp"].location,
            )
    finally:
        kb.close()

    return {"lead": lead}


async def write_node(state: OutreachState) -> dict:
    """Draft (or re-draft, using the verifier's critique) the outreach."""
    draft = await write_outreach(state["icp"], state["lead"], critique=state["critique"])
    return {"draft": draft, "attempts": state["attempts"] + 1}


async def verify_node(state: OutreachState) -> dict:
    """Adversarial check: every claim must trace to a finding."""
    assert state["draft"] is not None
    approved, critique = await verify_outreach(state["icp"], state["lead"], state["draft"])
    return {"approved": approved, "critique": critique or None}


# ---------- routing ----------

def route_after_verify(state: OutreachState) -> str:
    """Approved (or out of attempts) -> finish. Otherwise loop back to write."""
    if state["approved"] or state["attempts"] >= MAX_WRITE_ATTEMPTS:
        return "finish"
    return "rewrite"


def build_outreach_graph():
    """Compile the per-lead outreach graph."""
    graph = StateGraph(OutreachState)
    graph.add_node("research", research_node)
    graph.add_node("write", write_node)
    graph.add_node("verify", verify_node)

    graph.set_entry_point("research")
    graph.add_edge("research", "write")
    graph.add_edge("write", "verify")
    graph.add_conditional_edges(
        "verify", route_after_verify, {"rewrite": "write", "finish": END}
    )
    return graph.compile()


_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_outreach_graph()
    return _compiled_graph


# ---------- public API ----------

async def generate_outreach(icp: ICP, lead: Lead) -> Lead:
    """Run the full research->write->verify graph for one lead."""
    initial: OutreachState = {
        "icp": icp,
        "lead": lead,
        "draft": None,
        "critique": None,
        "attempts": 0,
        "approved": False,
    }
    final = await _get_graph().ainvoke(initial)

    lead = final["lead"]
    draft = final["draft"]
    if draft is not None:
        draft.approved = final["approved"]
        draft.critique = final["critique"]
        draft.attempts = final["attempts"]
        lead.outreach = draft
    return lead


async def generate_outreach_for_leads(
    icp: ICP, leads: list[Lead], concurrency: int = 2
) -> list[Lead]:
    """Run the outreach graph for many leads with bounded concurrency."""
    semaphore = asyncio.Semaphore(concurrency)

    async def _task(lead: Lead) -> Lead:
        async with semaphore:
            return await generate_outreach(icp, lead)

    return await asyncio.gather(*[_task(lead) for lead in leads])
