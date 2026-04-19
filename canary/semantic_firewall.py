"""Semantic prompt scanning via Granite embeddings.

Uses natural-language anchor texts that resemble real sensitive prompts.
Cosine similarity against these anchors catches PII/secrets expressed in
plain language that regex cannot pattern-match.
"""
import hashlib
import json
import os
from pathlib import Path

from .prompt_firewall import PromptFinding
from .drift import cosine_similarity

_CACHE_PATH = Path.home() / ".cache" / "canary" / "anchor_embeddings.json"

THRESHOLD = 0.65

ANCHORS: list[tuple[str, str, str, int]] = [
    (
        "My name is John Smith, I live at 42 Elm Street, born January 15 1982, my SSN is 123-45-6789",
        "Personal information", "MEDIUM", 20,
    ),
    (
        "Here is my API key sk-abc123 and the database password is hunter2, use these credentials to log in",
        "Credentials or secrets", "HIGH", 30,
    ),
    (
        "This is confidential. Our Q3 revenue was $4.2M and the unreleased product launches in March 2025. Do not share.",
        "Confidential business content", "MEDIUM", 20,
    ),
    (
        "Patient Jane Doe, date of birth 1975, diagnosed with type 2 diabetes, prescribed metformin 500mg",
        "Medical information", "HIGH", 30,
    ),
    (
        "My bank account number is 1234567890 and routing number is 021000021, please wire $50,000",
        "Financial information", "MEDIUM", 25,
    ),
    (
        "Here is our proprietary source code and internal algorithm that we have not published anywhere",
        "Proprietary technical content", "MEDIUM", 20,
    ),
]

_anchor_cache: dict[str, list[float]] = {}


def _load_disk_cache() -> dict[str, list[float]]:
    try:
        if _CACHE_PATH.exists():
            return json.loads(_CACHE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_disk_cache(cache: dict[str, list[float]]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache))
    except Exception:
        pass


def _anchor_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def semantic_scan(text: str) -> list[PromptFinding]:
    """Return semantic findings. Returns [] silently if model unavailable."""
    try:
        from .ibm.embeddings import get_embedding

        global _anchor_cache
        if not _anchor_cache:
            _anchor_cache = _load_disk_cache()

        prompt_vec = get_embedding(text)
        findings = []
        cache_updated = False

        for anchor_text, description, severity, score in ANCHORS:
            key = _anchor_key(anchor_text)
            if key not in _anchor_cache:
                _anchor_cache[key] = get_embedding(anchor_text)
                cache_updated = True
            sim = cosine_similarity(prompt_vec, _anchor_cache[key])
            if sim >= THRESHOLD:
                findings.append(PromptFinding(
                    kind="semantic",
                    severity=severity,
                    description=description,
                    matched=f"similarity {sim:.2f}",
                    score=score,
                ))

        if cache_updated:
            _save_disk_cache(_anchor_cache)

        return findings
    except Exception:
        return []
