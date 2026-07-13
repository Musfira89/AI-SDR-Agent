"""Export helpers — turn leads into CSV rows / a DataFrame."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import Lead

# Column order for exports (flat, human-friendly).
COLUMNS = [
    "name",
    "fit_score",
    "recommended",
    "score_reason",
    "rating",
    "reviews_count",
    "phone",
    "email",
    "website",
    "address",
    "category",
    "signals",
    "enrichment_status",
    "previously_seen",
    "email_subject",
    "email_body",
]


def lead_to_row(lead: Lead) -> dict:
    """Flatten one lead into a dict of simple values for CSV/table output."""
    data = lead.model_dump()
    data["signals"] = "; ".join(lead.signals)
    data["socials"] = "; ".join(f"{k}:{v}" for k, v in lead.socials.items())
    if lead.outreach is not None:
        data["email_subject"] = lead.outreach.subject
        data["email_body"] = lead.outreach.body
    return {col: data.get(col, "") for col in COLUMNS}


def export_to_csv(leads: list[Lead], path: str | Path) -> Path:
    """Write leads to a CSV file and return the path."""
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead_to_row(lead))
    return path
