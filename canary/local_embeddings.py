"""local granite embeddings via hugging face transformers."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from .device import detect_device_profile

MODEL_ID = "ibm-granite/granite-embedding-278m-multilingual"
LOCAL_DEPENDENCIES = [
    "transformers>=4.35",
    "torch>=2.0",
    "sentencepiece>=0.1.99",
    "protobuf>=4.0",
]

_model = None
_tokenizer = None
_device = None
_warned_slow = False


def missing_local_dependencies() -> list[str]:
    required = {
        "transformers": "transformers",
        "torch": "torch",
        "sentencepiece": "sentencepiece",
        "google.protobuf": "protobuf",
    }
    missing = []
    for module_name, package_name in required.items():
        if importlib.util.find_spec(module_name) is None:
            missing.append(package_name)
    return missing


def install_local_dependencies() -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *LOCAL_DEPENDENCIES],
        check=True,
    )


def _hf_cache_root() -> Path:
    base = Path.home() / ".cache" / "huggingface"
    if "HF_HOME" in os.environ:  # type: ignore[name-defined]
        base = Path(os.environ["HF_HOME"])  # type: ignore[name-defined]
    return base / "hub" / f"models--{MODEL_ID.replace('/', '--')}"


def local_model_cached() -> bool:
    snapshots = _hf_cache_root() / "snapshots"
    return snapshots.exists() and any(snapshots.iterdir())


def _load(*, local_only: bool | None = None):
    global _model, _tokenizer, _device
    if _model is not None:
        return
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
        from transformers.utils import logging as transformers_logging
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "local granite support is not installed. run `canary setup` "
            "or `pip install \"canary-watch[local]\"` and retry."
        ) from e

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        transformers_logging.set_verbosity_error()
        transformers_logging.disable_progress_bar()
    except Exception:
        pass

    attempts = [local_only] if local_only is not None else [True, False]
    last_error = None
    for local_files_only in attempts:
        try:
            _tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, local_files_only=local_files_only)
            _model = AutoModel.from_pretrained(MODEL_ID, local_files_only=local_files_only)
            break
        except Exception as e:  # pragma: no cover - error path depends on env
            last_error = e
    else:
        raise RuntimeError(
            "could not load the local granite model. download it during `canary setup`."
        ) from last_error

    if torch.backends.mps.is_available():
        _device = torch.device("mps")
    elif torch.cuda.is_available():
        _device = torch.device("cuda")
    else:
        _device = torch.device("cpu")

    _model = _model.to(_device)
    _model.eval()


def ensure_local_model(*, download_if_needed: bool) -> None:
    _load(local_only=(not download_if_needed))


def maybe_warn_slow_local(profile=None) -> str | None:
    global _warned_slow
    profile = profile or detect_device_profile()
    if profile.local_warning and not _warned_slow:
        _warned_slow = True
        return "local mode will run exceptionally slower on this device"
    return None


def get_local_embedding(text: str) -> list[float]:
    """return a 768-dim embedding using the local granite model."""
    import torch

    profile = detect_device_profile()
    warning = maybe_warn_slow_local(profile)
    if warning:
        from .ui import warn

        warn(warning, profile.summary)

    _load()
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(_device)
    with torch.no_grad():
        output = _model(**inputs)
    return output.last_hidden_state.mean(dim=1).squeeze().tolist()
