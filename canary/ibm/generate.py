"""IBM watsonx.ai text generation via Granite chat model."""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

from .iam import get_iam_token

REGION_HOSTS = {
    "us-south": "us-south.ml.cloud.ibm.com",
    "eu-de":    "eu-de.ml.cloud.ibm.com",
    "jp-tok":   "jp-tok.ml.cloud.ibm.com",
    "eu-gb":    "eu-gb.ml.cloud.ibm.com",
    "au-syd":   "au-syd.ml.cloud.ibm.com",
}

CHAT_MODEL_ID = "ibm/granite-3-8b-instruct"

_CACHE_PATH = Path.home() / ".cache" / "canary" / "generate_cache.json"
_mem_cache: dict[str, str] = {}


def _endpoint() -> str:
    region = os.environ.get("IBM_REGION", "us-south").strip() or "us-south"
    host = REGION_HOSTS.get(region, REGION_HOSTS["us-south"])
    return f"https://{host}/ml/v1/text/chat?version=2024-05-31"


def _cache_key(messages: list[dict]) -> str:
    payload = json.dumps({"model": CHAT_MODEL_ID, "messages": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _load_disk_cache() -> dict[str, str]:
    try:
        if _CACHE_PATH.exists():
            return json.loads(_CACHE_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_disk_cache(cache: dict[str, str]) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps(cache))
    except Exception:
        pass


def chat_completion(messages: list[dict], *, max_tokens: int = 512) -> str:
    """Send a chat request to Granite and return the assistant message content.

    Results are cached by (model, messages) SHA256 so repeated identical
    prompts — e.g. auditing the same bash command twice — never hit the API.
    """
    global _mem_cache

    key = _cache_key(messages)

    if not _mem_cache:
        _mem_cache = _load_disk_cache()
    if key in _mem_cache:
        return _mem_cache[key]

    from ..usage import check_and_increment
    check_and_increment("generate")

    project_id = os.environ.get("IBM_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "online mode is not configured. add your project settings to `.env`, "
            "or switch to `canary mode local`."
        )

    token = get_iam_token()
    resp = None
    for attempt in range(4):
        resp = requests.post(
            _endpoint(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "model_id": CHAT_MODEL_ID,
                "project_id": project_id,
                "messages": messages,
                "max_tokens": max_tokens,
            },
            timeout=30,
        )
        if resp.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        resp.raise_for_status()
        break

    result = resp.json()["choices"][0]["message"]["content"]
    _mem_cache[key] = result
    _save_disk_cache(_mem_cache)
    return result
