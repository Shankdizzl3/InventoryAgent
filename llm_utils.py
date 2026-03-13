"""
llm_utils.py — Shared Ollama LLM utilities.

Provides a single-turn LLM call for the investigation layer (no tools, no streaming).
Also used by agent.py for client setup.
"""

import os
import re

import ollama
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi4-mini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def get_client() -> ollama.AsyncClient:
    """Return an async Ollama client pointed at the configured base URL."""
    return ollama.AsyncClient(host=OLLAMA_BASE_URL)


async def call_llm_single_turn(system: str, user: str) -> str:
    """
    Single-turn LLM call — no tools, no streaming.
    Returns the raw content string from the model.
    """
    client = get_client()
    response = await client.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.message.content or ""


def parse_verdict(raw: str) -> dict:
    """
    Parse LLM output into a structured verdict dict.
    Tolerant of filler text — extracts verdict/reason/new_category via regex.

    Returns:
        {"verdict": "CONFIRM"|"ESCALATE"|"RECLASSIFY"|"UNKNOWN",
         "reason": str,
         "new_category": str or ""}
    """
    text = raw.strip()

    # Extract verdict
    verdict = "UNKNOWN"
    m = re.search(r"(?i)\bverdict\s*[:=]\s*(CONFIRM|ESCALATE|RECLASSIFY)\b", text)
    if m:
        verdict = m.group(1).upper()

    # Extract reason
    reason = ""
    m = re.search(r"(?i)\breason\s*[:=]\s*(.+?)(?:\n|$)", text)
    if m:
        reason = m.group(1).strip().rstrip(".")

    # Extract new_category (only for RECLASSIFY)
    new_category = ""
    if verdict == "RECLASSIFY":
        m = re.search(r"(?i)\bnew_category\s*[:=]\s*(\S+)", text)
        if m:
            new_category = m.group(1).strip()

    return {
        "verdict": verdict,
        "reason": reason or text[:200],
        "new_category": new_category,
    }
