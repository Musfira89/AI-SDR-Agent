"""Lead memory — the agent remembers every lead it has ever processed.

Why this matters: a real SDR never contacts the same business twice by
accident. This module gives the agent persistent memory across runs using
SQLite (zero setup, ships with Python):

  - every processed lead is fingerprinted (normalized name + address)
  - on the next run, already-seen leads are flagged (or skipped)
  - near-duplicate leads inside one batch are removed with fuzzy matching

In Phase 2 this upgrades to semantic (embedding-based) dedup in a vector DB;
Phase 1 keeps it simple and dependency-free.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from .models import Lead

DB_PATH = Path("leads_memory.db")
FUZZY_THRESHOLD = 0.92  # names more similar than this are treated as duplicates


def _normalize(text: str | None) -> str:
    """Lowercase and strip everything except letters/digits — stable for matching."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def fingerprint(lead: Lead) -> str:
    """A stable ID for a business: normalized name + address."""
    return f"{_normalize(lead.name)}|{_normalize(lead.address)}"


class LeadMemory:
    """Persistent 'seen leads' store backed by SQLite."""

    def __init__(self, path: Path | str = DB_PATH) -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_leads (
                fingerprint TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                first_seen  TEXT NOT NULL,
                times_seen  INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        self._conn.commit()

    def is_seen(self, lead: Lead) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM seen_leads WHERE fingerprint = ?", (fingerprint(lead),)
        ).fetchone()
        return row is not None

    def mark_seen(self, lead: Lead) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO seen_leads (fingerprint, name, first_seen)
            VALUES (?, ?, ?)
            ON CONFLICT(fingerprint)
            DO UPDATE SET times_seen = times_seen + 1
            """,
            (fingerprint(lead), lead.name, now),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def dedupe_batch(leads: list[Lead]) -> list[Lead]:
    """Remove near-duplicates within one batch (e.g. 'Smile Dental' vs
    'Smile Dental Clinic LLC' at the same address). Keeps the first seen."""
    kept: list[Lead] = []
    for lead in leads:
        is_duplicate = False
        for existing in kept:
            same_address = (
                _normalize(lead.address) == _normalize(existing.address)
                and lead.address is not None
            )
            name_similarity = SequenceMatcher(
                None, _normalize(lead.name), _normalize(existing.name)
            ).ratio()
            if name_similarity >= FUZZY_THRESHOLD and (same_address or not lead.address):
                is_duplicate = True
                break
        if not is_duplicate:
            kept.append(lead)
    return kept
