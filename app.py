"""Streamlit UI for the AI SDR Agent.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from sdr_agent.config import DEFAULT_ICP
from sdr_agent.graph import generate_outreach_for_leads
from sdr_agent.knowledge_base import KnowledgeBase
from sdr_agent.models import ICP
from sdr_agent.pipeline import run_pipeline
from sdr_agent.storage import COLUMNS, lead_to_row

st.set_page_config(page_title="AI SDR Agent", layout="wide")

st.title("AI SDR Agent")
st.caption(
    "Autonomous sales prospecting: discover businesses that match your ideal "
    "customer profile, qualify them with AI scoring, and generate verified, "
    "personalized outreach."
)

# --- Sidebar: define the ICP + offer ---
with st.sidebar:
    st.header("Ideal Customer Profile")
    industry = st.text_input("Industry", DEFAULT_ICP.industry)
    location = st.text_input("Location", DEFAULT_ICP.location)
    offer = st.text_area("Your offer (what you sell)", DEFAULT_ICP.offer, height=80)
    ideal_description = st.text_area(
        "What makes a good fit?", DEFAULT_ICP.ideal_description, height=90
    )
    signals_raw = st.text_area(
        "Buying signals (one per line)",
        "\n".join(DEFAULT_ICP.signals_to_look_for),
        height=90,
    )
    limit = st.slider("Number of leads", min_value=5, max_value=20, value=10)
    skip_seen = st.checkbox(
        "Skip previously-seen leads",
        value=True,
        help="The agent remembers leads from earlier runs and won't process them twice.",
    )
    run = st.button("Find Leads", type="primary", use_container_width=True)

    st.divider()
    st.header("Knowledge Base")
    kb_query = st.text_input(
        "Search accumulated research",
        help="Everything the agent learns during research is stored and searchable here.",
    )
    if kb_query:
        kb = KnowledgeBase()
        try:
            hits = kb.search(kb_query, k=5)
        finally:
            kb.close()
        if hits:
            for hit in hits:
                st.markdown(f"**{hit['lead']}** · relevance {hit['score']}\n\n{hit['text']}")
        else:
            st.caption("No knowledge stored yet — generate outreach first.")


def _current_icp() -> ICP:
    return ICP(
        industry=industry,
        location=location,
        offer=offer,
        ideal_description=ideal_description,
        signals_to_look_for=[s.strip() for s in signals_raw.splitlines() if s.strip()],
    )


# --- Lead discovery pipeline ---
if run:
    status = st.empty()
    try:
        with st.spinner("Working..."):
            leads = asyncio.run(
                run_pipeline(
                    _current_icp(),
                    limit=limit,
                    skip_seen=skip_seen,
                    on_progress=lambda msg: status.info(msg),
                )
            )
        st.session_state["leads"] = leads
        st.session_state.pop("outreach_leads", None)
        status.success(f"Done — {len(leads)} leads processed.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Something went wrong: {exc}")
        st.stop()

leads = st.session_state.get("leads")

if leads is None:
    st.info("Set your Ideal Customer Profile in the sidebar and click **Find Leads**.")
    st.stop()

if not leads:
    st.warning(
        "No new leads found. Try a broader industry/location, or untick "
        "'Skip previously-seen leads'."
    )
    st.stop()

# --- Results ---
st.subheader("Qualified Leads")

recommended = [l for l in leads if l.recommended]
col1, col2, col3 = st.columns(3)
col1.metric("Total leads", len(leads))
col2.metric("Recommended", len(recommended))
scored = [l.fit_score for l in leads if l.fit_score is not None]
col3.metric("Average fit score", round(sum(scored) / len(scored)) if scored else 0)

df = pd.DataFrame([lead_to_row(l) for l in leads], columns=COLUMNS)
st.dataframe(df, use_container_width=True, hide_index=True)
st.download_button(
    "Download CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="leads.csv",
    mime="text/csv",
)

# --- Research + outreach generation ---
st.divider()
st.subheader("Personalized Outreach")
st.caption(
    "For each selected lead the agent researches the business, drafts a "
    "personalized email sequence, and passes it through an adversarial "
    "verifier that rejects any draft containing unsupported claims."
)

top_n = st.slider(
    "Generate outreach for the top N recommended leads",
    min_value=1,
    max_value=max(len(recommended), 1),
    value=min(3, max(len(recommended), 1)),
    disabled=not recommended,
)

if st.button("Research & Write Outreach", disabled=not recommended):
    targets = recommended[:top_n]
    status2 = st.empty()
    status2.info(
        f"Researching and writing for {len(targets)} lead(s) — each runs a "
        "research, write, verify cycle."
    )
    try:
        with st.spinner("Agents working..."):
            done = asyncio.run(generate_outreach_for_leads(_current_icp(), targets))
        st.session_state["outreach_leads"] = done
        status2.success("Outreach generated.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Outreach generation failed: {exc}")

for lead in st.session_state.get("outreach_leads", []):
    if lead.outreach is None:
        continue
    verdict = (
        "Verified"
        if lead.outreach.approved
        else f"Needs review ({lead.outreach.attempts} attempts)"
    )
    with st.expander(f"{lead.name} — {verdict}"):
        st.markdown(f"**Subject:** {lead.outreach.subject}")
        st.markdown(lead.outreach.body)
        st.markdown(f"**Follow-up 1:** {lead.outreach.followup_1}")
        st.markdown(f"**Follow-up 2:** {lead.outreach.followup_2}")
        if lead.outreach.cited_facts:
            st.caption("Facts referenced: " + " · ".join(lead.outreach.cited_facts))
        if lead.outreach.critique:
            st.caption(f"Verifier notes: {lead.outreach.critique}")
        st.caption(f"Research findings used: {len(lead.findings)}")
