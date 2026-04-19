"""Demo agent binary used by the live demo.

This is intentionally tiny and deterministic: it exercises the real Canary
guard shim, hook commands, audit pipeline, and watcher by emitting the same
hook payload shape that Claude Code uses.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _load_settings() -> dict:
    try:
        return json.loads(_settings_path().read_text())
    except Exception:
        return {}


def _run_hooks(event_name: str, matcher: str, payload: dict) -> None:
    settings = _load_settings()
    for block in settings.get("hooks", {}).get(event_name, []):
        if block.get("matcher") != matcher:
            continue
        for hook in block.get("hooks", []):
            command = hook.get("command")
            if not command:
                continue
            subprocess.run(
                command,
                input=json.dumps(payload),
                text=True,
                shell=True,
                check=False,
            )


def _pre(tool_name: str, tool_input: dict) -> None:
    _run_hooks("PreToolUse", tool_name, {"tool_name": tool_name, "tool_input": tool_input})


def _post(tool_name: str, tool_input: dict, tool_response: dict) -> None:
    _run_hooks(
        "PostToolUse",
        tool_name,
        {"tool_name": tool_name, "tool_input": tool_input, "tool_response": tool_response},
    )


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _demo_session(project: Path) -> int:
    routes_dir = project / "routes"
    auth_dir = project / "src" / "auth"

    print("demo agent: starting session", flush=True)

    read_cmd = "ls routes"
    _pre("Bash", {"command": read_cmd})
    listing = "\n".join(sorted(p.name for p in routes_dir.iterdir() if p.is_file()))
    _post("Bash", {"command": read_cmd}, {"output": listing})

    # Give `canary watch` time to notice the first tool event, build the
    # baseline, and create the automatic checkpoint before edits begin.
    time.sleep(float(os.environ.get("CANARY_DEMO_BASELINE_WAIT", "2.5")))

    mkdir_cmd = "mkdir -p src/auth"
    _pre("Bash", {"command": mkdir_cmd})
    auth_dir.mkdir(parents=True, exist_ok=True)
    _post("Bash", {"command": mkdir_cmd}, {"output": ""})

    middleware = """\
const jwt = require("jsonwebtoken");

function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";

  if (!token) {
    return res.status(401).json({ error: "missing token" });
  }

  try {
    req.user = jwt.verify(token, process.env.JWT_SECRET || "demo-secret");
    return next();
  } catch (err) {
    return res.status(401).json({ error: "invalid token" });
  }
}

module.exports = { requireAuth };
"""
    middleware_path = auth_dir / "middleware.js"
    _pre("Write", {"file_path": str(middleware_path), "content": middleware})
    _write_file(middleware_path, middleware)

    orders = """\
const express = require("express");
const { requireAuth } = require("../src/auth/middleware");

const router = express.Router();

router.get("/orders", requireAuth, (req, res) => {
  res.json({ ok: true, user: req.user || null, orders: [] });
});

module.exports = router;
"""
    orders_path = routes_dir / "orders.js"
    _pre("Edit", {"file_path": str(orders_path), "new_string": orders})
    _write_file(orders_path, orders)

    payments = """\
const express = require("express");
const { requireAuth } = require("../src/auth/middleware");

const router = express.Router();

router.post("/payments", requireAuth, (req, res) => {
  res.json({ ok: true, accepted: true });
});

module.exports = router;
"""
    payments_path = routes_dir / "payments.js"
    _pre("Edit", {"file_path": str(payments_path), "new_string": payments})
    _write_file(payments_path, payments)

    package_json_path = project / "package.json"
    package_json = json.dumps(
        {
            "name": "demo-api-project",
            "private": True,
            "dependencies": {
                "express": "^4.21.0",
                "jsonwebtoken": "^9.0.2",
            },
        },
        indent=2,
    ) + "\n"
    _pre("Edit", {"file_path": str(package_json_path), "new_string": package_json})
    _write_file(package_json_path, package_json)

    test_cmd = "npm test"
    test_output = "PASS tests/auth.test.js\nPASS tests/orders.test.js"
    _pre("Bash", {"command": test_cmd})
    _post("Bash", {"command": test_cmd}, {"output": test_output})

    # Let the watcher flush the last few events before the process exits.
    time.sleep(1.5)
    print("demo agent: session complete", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    prompt = argv[0] if argv else ""
    project = Path.cwd()

    print(f"demo agent received prompt: {prompt}", flush=True)
    return _demo_session(project)


if __name__ == "__main__":
    raise SystemExit(main())
