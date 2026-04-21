"""Checkpoint snapshots and rollback. Rollback is itself reversible."""
import json
import os
import shutil
import time

CANARY_DIR = ".canary"
CHECKPOINTS_DIRNAME = "checkpoints"
IGNORE_NAMES = (".canary", ".git", "node_modules", "__pycache__", "venv", ".venv", "dist", "build")


def _canary_dir(target: str) -> str:
    return os.path.join(target, CANARY_DIR)


def _checkpoints_dir(target: str) -> str:
    return os.path.join(_canary_dir(target), CHECKPOINTS_DIRNAME)


def _write_gitignore(target: str) -> None:
    """Drop a .gitignore inside .canary/ so session data doesn't leak into git."""
    cdir = _canary_dir(target)
    os.makedirs(cdir, exist_ok=True)
    gi = os.path.join(cdir, ".gitignore")
    if not os.path.exists(gi):
        with open(gi, "w") as f:
            f.write("# canary session data — not for version control\n*\n")


def _normalize_checkpoint_name(name: str) -> str:
    checkpoint_id = name.strip()
    if not checkpoint_id:
        raise RuntimeError("Checkpoint name required.")
    separators = [sep for sep in (os.sep, os.altsep) if sep]
    if any(sep in checkpoint_id for sep in separators):
        raise RuntimeError("Checkpoint names cannot include path separators.")
    if checkpoint_id in {".", ".."}:
        raise RuntimeError("Checkpoint name is invalid.")
    return checkpoint_id


def take_snapshot(target: str, name: str | None = None) -> str:
    """Copy every non-ignored file from target to .canary/checkpoints/<id>/."""
    _write_gitignore(target)
    cps = _checkpoints_dir(target)
    os.makedirs(cps, exist_ok=True)
    checkpoint_id = _normalize_checkpoint_name(name) if name is not None else f"checkpoint_{int(time.time())}"
    dest = os.path.join(cps, checkpoint_id)
    if os.path.exists(dest):
        raise RuntimeError(f"Checkpoint '{checkpoint_id}' already exists.")
    shutil.copytree(
        target,
        dest,
        ignore=shutil.ignore_patterns(*IGNORE_NAMES),
    )
    meta = {"id": checkpoint_id, "timestamp": time.time(), "target": os.path.abspath(target)}
    with open(os.path.join(dest, ".canary_meta.json"), "w") as f:
        json.dump(meta, f)
    return checkpoint_id


def list_checkpoints(target: str = ".") -> list[dict]:
    cps = _checkpoints_dir(target)
    if not os.path.exists(cps):
        return []
    out = []
    for name in sorted(os.listdir(cps)):
        meta_path = os.path.join(cps, name, ".canary_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                out.append(json.load(f))
    return out


def delete_checkpoint(target: str, checkpoint_id: str) -> bool:
    """Delete a single checkpoint by id. Returns True if it existed."""
    path = os.path.join(_checkpoints_dir(target), checkpoint_id)
    if not os.path.exists(path):
        return False
    shutil.rmtree(path)
    return True


def delete_all_checkpoints(target: str) -> int:
    """Delete every checkpoint. Returns the count removed."""
    checkpoints = list_checkpoints(target)
    for c in checkpoints:
        shutil.rmtree(os.path.join(_checkpoints_dir(target), c["id"]), ignore_errors=True)
    return len(checkpoints)


def rollback(target: str, checkpoint_id: str | None = None) -> tuple[str, str]:
    """Revert target to the given (or most recent) checkpoint.

    Returns (restored_id, backup_id). The current state is snapshotted as
    `rollback_backup_<epoch>` before restoring, making rollback reversible.
    """
    checkpoints = list_checkpoints(target)
    if not checkpoints:
        raise RuntimeError("No checkpoints found. Run `canary watch` first.")

    if checkpoint_id is None:
        checkpoint = checkpoints[-1]
    else:
        matches = [c for c in checkpoints if c["id"] == checkpoint_id]
        if not matches:
            raise RuntimeError(f"Checkpoint '{checkpoint_id}' not found.")
        checkpoint = matches[0]

    # Back up current state first
    backup_id = f"rollback_backup_{int(time.time())}"
    take_snapshot(target, backup_id)

    # Restore
    src = os.path.join(_checkpoints_dir(target), checkpoint["id"])
    for item in os.listdir(src):
        if item == ".canary_meta.json":
            continue
        s = os.path.join(src, item)
        d = os.path.join(target, item)
        if os.path.isdir(s):
            if os.path.exists(d):
                shutil.rmtree(d)
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    return checkpoint["id"], backup_id
