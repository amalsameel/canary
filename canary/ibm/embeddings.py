"""Local IBM Granite embeddings with sha256 cache."""
import hashlib
import os

# In-memory cache: sha256(content) -> embedding vector
_cache: dict[str, list[float]] = {}


def _env_true(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"

def _mock_embedding(text: str) -> list[float]:
    """Return a deterministic 768-dim embedding for offline demos/tests."""
    seed = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
    out: list[float] = []
    counter = 0
    while len(out) < 768:
        chunk = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        for idx in range(0, len(chunk), 4):
            value = int.from_bytes(chunk[idx:idx + 4], "big") / 0xFFFFFFFF
            out.append((value * 2.0) - 1.0)
            if len(out) == 768:
                break
        counter += 1
    return out


def get_embedding(text: str) -> list[float]:
    """Return a 768-dim embedding for `text`, cached by sha256."""
    key = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    if key in _cache:
        return _cache[key]
    if _env_true("IBM_MOCK"):
        vec = _mock_embedding(text)
        _cache[key] = vec
        return vec
    from ..local_embeddings import get_local_embedding

    vec = get_local_embedding(text)
    _cache[key] = vec
    return vec
