# Autonomous AI SDR Agent

An AI Sales Development Representative that automates top-of-funnel prospecting:
given an **Ideal Customer Profile (ICP)** and an **offer**, it **discovers** matching
local businesses, **enriches** each from its website, and **scores** how well each
fits — turning hours of manual research into minutes.

---

## Lead engine

| Stage | What happens |
|-------|--------------|
| **Discovery** | Finds real businesses matching the ICP (Serper "places" search) |
| **Dedup + Memory** | Removes near-duplicates and remembers every lead across runs (SQLite) — never processes the same business twice |
| **Enrichment** | Scrapes each website concurrently for email, socials, and opportunity signals |
| **Scoring** | An LLM (Groq · Llama-3.3-70B) scores fit 0–100 with a grounded reason |
| **Output** | A sorted, scored lead table + one-click CSV export |

The whole thing runs on **free-tier** services and scrapes **only public data**.

## Outreach engine

| Stage | What happens |
|-------|--------------|
| **Deep research** | A researcher agent runs targeted web searches per lead and collects findings (each with its source) |
| **Outreach writing** | A writer drafts a personalized email + 2 follow-ups using ONLY verified findings |
| **Adversarial verification** | A verifier checks every claim traces to a finding; rejected drafts loop back with critique (LangGraph state machine) |
| **Knowledge base** | Every finding accumulates in a searchable market knowledge base (a from-scratch TF-IDF vector store) |

```
research → write → verify ──approved──▶ done
              ▲          │
              └──critique─┘   (reflection loop, max 2 attempts)
```

---

## Architecture

```
ICP + offer
    │
    ▼
 discovery.py   → finds businesses (name, phone, website, rating)
    │
    ▼
 memory.py      → batch dedup + persistent "seen leads" store (SQLite)
    │
    ▼
 enrichment.py  → scrapes websites concurrently (email, socials, signals)
    │
    ▼
 scoring.py     → Groq LLM scores fit (0–100) + reason, grounded in real data,
    │             JSON mode + retry-with-backoff for rate limits
    ▼
 UI / CSV       → sorted lead list you can act on
```

Async + semaphores let enrichment and scoring run in parallel without hitting rate limits.

---

## Setup

1. **Clone & install**
   ```bash
   pip install -r requirements.txt
   ```

2. **Add your free API keys** — copy `.env.example` to `.env` and fill in:
   - `GROQ_API_KEY` — from https://console.groq.com/keys
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

## Configuring the target

Everything is configurable — set the ICP in the sidebar (industry, location, offer,
what makes a good fit, buying signals). Point it at **any** local vertical: dental
clinics, salons, HVAC, law firms, med-spas, and so on. The LLM is configurable via
`GROQ_MODEL` in `.env` (default `llama-3.3-70b-versatile`).

---

## Design decisions worth noting

- **Grounded scoring** — the scoring prompt forbids inventing facts; the model may
  only reason over data the pipeline actually collected.
- **Persistent lead memory** — a real SDR never contacts the same business twice;
  the agent fingerprints every processed lead and skips it on future runs.
- **Failure isolation** — one bad website or one failed LLM call never crashes the
  batch; errors are recorded per-lead and the pipeline continues.
- **Rate-limit resilience** — LLM calls use JSON mode plus exponential backoff with jitter.

---

## Ethics & compliance

- Uses only **publicly available** business data; no logins, no personal data.
- Produces drafts/lists for **human review** — it does not mass-send anything.
- Respects timeouts and reasonable request behaviour.

---

## Tech stack

Python · httpx (async) · BeautifulSoup · Pydantic v2 · Groq (Llama-3.3-70B) · Serper · SQLite · Streamlit
