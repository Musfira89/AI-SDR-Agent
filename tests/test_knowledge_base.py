"""Quick test for the from-scratch TF-IDF knowledge base.

Run from the project root:  python tests/test_knowledge_base.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdr_agent.knowledge_base import KnowledgeBase  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        kb = KnowledgeBase(Path(tmp) / "kb_test.db")

        kb.add("Bright Smiles Dental has excellent patient reviews and offers implants.",
               "http://example.com/1", "Bright Smiles Dental", "Austin")
        kb.add("Austin Family Dentistry recently opened a second location downtown.",
               "http://example.com/2", "Austin Family Dentistry", "Austin")
        kb.add("The clinic's website has no online booking option visible.",
               "website", "Bright Smiles Dental", "Austin")

        # Exact duplicate should be skipped
        kb.add("Bright Smiles Dental has excellent patient reviews and offers implants.",
               "http://example.com/1", "Bright Smiles Dental", "Austin")

        assert kb.count() == 3, f"Expected 3 docs, got {kb.count()}"

        hits = kb.search("which clinic has no online booking?", k=2)
        assert hits, "Search returned nothing"
        assert "booking" in hits[0]["text"].lower(), f"Bad top hit: {hits[0]}"

        hits2 = kb.search("patient reviews implants", k=2)
        assert "implants" in hits2[0]["text"].lower(), f"Bad top hit: {hits2[0]}"

        kb.close()
        print("KNOWLEDGE BASE TEST PASSED —", "3 docs stored, dedup + retrieval working")


if __name__ == "__main__":
    main()
