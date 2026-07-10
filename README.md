# Autonomous AI SDR Agent

An AI Sales Development Representative that automates top-of-funnel prospecting:
given an **Ideal Customer Profile (ICP)** and an **offer**, it **discovers** matching
local businesses, **enriches** each from its website, and **scores** how well each
fits — turning hours of manual research into minutes.

> **Status:** Phase 1 complete (discover → enrich → score → export).
> Phase 2 adds deep per-lead research, multi-agent orchestration, and personalized outreach.

---

## What it does (Phase 1)

| Stage | What happens |
|-------|--------------|
| **Discovery** | Finds real businesses matching the ICP (Serper "places" search) |
| **Enrichment** | Scrapes each website for email, socials, and opportunity signals |
| **Scoring** | An LLM (Gemini) scores fit 0–100 with a grounded reason |
| **Output** | A sorted, scored lead table + one-click CSV export |

The whole thing runs on **free-tier** services and scrapes **only public data**.

---

## Architecture

```
ICP + offer
    │
    ▼
 discovery.py   → finds businesses (name, phone, website, rating)
    │
    ▼
 enrichment.py  → scrapes websites concurrently (email, socials, signals)
    │
    ▼
 scoring.py     → Gemini scores fit (0–100) + reason, grounded in real data
    │
    ▼
 UI / CSV       → sorted lead list you can act on
```

Async + a semaphore let enrichment and scoring run in parallel without hitting rate limits.

---

##  Setup

1. **Clone & install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your free API keys** — copy `.env.example` to `.env` and fill in:
   - `GEMINI_API_KEY` — from https://aistudio.google.com/app/apikey
   - `SERPER_API_KEY` — from https://serper.dev

3. **Run the app**
   ```bash
   streamlit run app.py
   ```
   …or test from the terminal:
   ```bash
   python run_cli.py
   ```

---
