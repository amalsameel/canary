"""ibm cloud iam token acquisition with in-memory caching.

tokens are valid for ~1 hour. we refresh 60 s before expiry to avoid edge-case 401s.
"""
import time
import os
import requests

_token_cache = {"token": None, "expires_at": 0.0}


def get_iam_token() -> str:
    """return a valid ibm iam bearer token, refreshing if needed."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    api_key = os.environ.get("IBM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "online mode is not configured. add your cloud credentials to `.env`, "
            "or switch to `canary mode local`."
        )

    resp = requests.post(
        "https://iam.cloud.ibm.com/identity/token",
        data={
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 3600))
    return _token_cache["token"]
