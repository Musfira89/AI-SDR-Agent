"""Streamlit UI for the AI SDR Agent (Phase 1).

Run with:  streamlit run app.py
"""

from __future__ import annotations

import asyncio

import pandas as pd
import streamlit as st

from sdr_agent.config import DEFAULT_ICP
from sdr_agent.models import ICP
from sdr_agent.pipeline import run_pipeline
from sdr_agent.storage import COLUMNS, lead_to_row

st.set_page_config(page_title="AI SDR Agent", page_icon="🤖", layout="wide")

st.title("🤖 Autonomous AI SDR Agent — Phase 1")
st.caption("Find → enrich → score local business leads against your Ideal Customer Profile.")

# --- Sidebar: define the ICP + offer ---
with st.sidebar:
    st.header("🎯 Ideal Customer Profile")
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
    run = st.button("🚀 Find Leads", type="primary", use_container_width=True)

if run:
    icp = ICP(
        industry=industry,
        location=location,
        offer=offer,
        ideal_description=ideal_description,
        signals_to_look_for=[s.strip() for s in signals_raw.splitlines() if s.strip()],
    )

    status = st.empty()
    try:
        with st.spinner("Working..."):
            leads = asyncio.run(
                run_pipeline(icp, limit=limit, on_progress=lambda msg: status.info(msg))
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Something went wrong: {exc}")
        st.stop()

    status.success(f"Done — {len(leads)} leads processed.")

    if not leads:
        st.warning("No leads found. Try a broader industry or location.")
        st.stop()

    # Summary metrics
    recommended = [l for l in leads if l.recommended]
    col1, col2, col3 = st.columns(3)
    col1.metric("Total leads", len(leads))
    col2.metric("Recommended", len(recommended))
    scored = [l.fit_score for l in leads if l.fit_score is not None]
    col3.metric("Avg fit score", round(sum(scored) / len(scored)) if scored else 0)

    # Results table
    df = pd.DataFrame([lead_to_row(l) for l in leads], columns=COLUMNS)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Download
    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name="leads.csv",
        mime="text/csv",
    )
else:
    st.info("👈 Set your Ideal Customer Profile in the sidebar and click **Find Leads**.")
