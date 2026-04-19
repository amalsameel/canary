"""ibm granite embedding call with sha256 cache and region selection.

modes (set in `.env`):
  IBM_LOCAL=true  — real granite model running on-device via hugging face
  (neither)       — ibm hosted api via watsonx.ai (default)
"""
import hashlib
import os
import time
import requests

from .iam import get_iam_token

# In-memory cache: sha256(content) -> embedding vector
_cache: dict[str, list[float]] = {}

REGION_HOSTS = {
    "us-south": "us-south.ml.cloud.ibm.com",
    "eu-de":    "eu-de.ml.cloud.ibm.com",
    "jp-tok":   "jp-tok.ml.cloud.ibm.com",
    "eu-gb":    "eu-gb.ml.cloud.ibm.com",
    "au-syd":   "au-syd.ml.cloud.ibm.com",
}

MODEL_ID = "ibm/granite-embedding-278m-multilingual"
MAX_INPUT_CHARS = 8000  # Granite has a token cap; 8k chars is safely under it


def _env_true(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"


def _endpoint() -> str:
    region = os.environ.get("IBM_REGION", "us-south").strip() or "us-south"
    host = REGION_HOSTS.get(region, REGION_HOSTS["us-south"])
    return f"https://{host}/ml/v1/text/embeddings?version=2024-05-31"


def get_embedding(text: str) -> list[float]:
    """return a 768-dim embedding for `text`, cached by sha256."""
    key = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    if key in _cache:
        return _cache[key]
    if _env_true("IBM_LOCAL"):
        from ..local_embeddings import get_local_embedding
        vec = get_local_embedding(text)
        _cache[key] = vec
        return vec

    project_id = os.environ.get("IBM_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "online mode is not configured. add your project settings to `.env`, "
            "or switch to `canary mode local`."
        )

    from ..usage import check_and_increment
    check_and_increment("embed")

    token = get_iam_token()
    for attempt in range(4):
        resp = requests.post(
            _endpoint(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "model_id": MODEL_ID,
                "project_id": project_id,
                "inputs": [text[:MAX_INPUT_CHARS]],
            },
            timeout=30,
        )
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        break
    vector = resp.json()["results"][0]["embedding"]
    _cache[key] = vector
    return vector
