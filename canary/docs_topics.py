"""built-in documentation topics for `canary docs`."""

DOC_TOPICS = {
    "install": {
        "summary": "package install and first-run setup",
        "lines": [
            "  pip install canary-watch",
            "  canary setup",
            "",
            "  install the base package first.",
            "  `canary setup` then profiles the device and installs local support",
            "  only if the machine is a good fit for on-device granite.",
        ],
    },
    "setup": {
        "summary": "hardware-aware setup flow",
        "lines": [
            "  canary setup",
            "  canary setup --prefer local",
            "  canary setup --prefer online",
            "",
            "  on stronger laptops, canary can install the local stack and",
            "  download granite for you.",
            "  on slower devices, canary keeps you on online mode unless you",
            "  explicitly continue.",
        ],
    },
    "backends": {
        "summary": "local and online backend behavior",
        "lines": [
            "  local   on-device granite via hugging face",
            "  online  managed cloud inference via watsonx.ai",
            "",
            "  `canary mode local` can install and download local support when needed.",
            "  on slower laptops, canary warns before enabling local mode.",
        ],
    },
    "guard": {
        "summary": "direct claude code integration",
        "lines": [
            "  canary guard install",
            "  canary guard status",
            "  export PATH=\"$HOME/.canary/bin:$PATH\"",
            "",
            "  this installs a `claude` shim in front of the real binary",
            "  so command-line prompts are checked before they reach the agent.",
        ],
    },
    "wrappers": {
        "summary": "safe wrapper command for claude code",
        "lines": [
            "  claude-safe \"refactor auth flow\"",
            "  claude-safe --watch \"fix the login bug\"",
            "",
            "  gates the initial prompt, then launches claude with the same prompt.",
        ],
    },
    "watch": {
        "summary": "filesystem watchdog usage",
        "lines": [
            "  canary watch .",
            "  canary rollback .",
            "  canary checkpoints .",
            "",
            "  canary snapshots the workspace, watches for drift, and lets you",
            "  roll back to a clean checkpoint if the agent goes off the rails.",
        ],
    },
}
