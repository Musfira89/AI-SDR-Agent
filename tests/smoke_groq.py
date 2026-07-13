"""Smoke test — verifies the Groq key + JSON mode work end-to-end.

Run from the project root:  python tests/smoke_groq.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sdr_agent.scoring import _call_llm  # noqa: E402


async def main() -> None:
    reply = await _call_llm(
        'Health check. Respond in JSON with exactly: {"status": "ok", "model_working": true}'
    )
    data = json.loads(reply)
    assert data.get("status") == "ok", f"Unexpected reply: {data}"
    print("GROQ SMOKE TEST PASSED:", data)


if __name__ == "__main__":
    asyncio.run(main())
