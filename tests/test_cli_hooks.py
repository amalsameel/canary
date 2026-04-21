from canary.cli import _all_hooks_installed, _bash_permission_allow_rules, _install_hook


def test_install_hook_upgrades_partial_legacy_hook_set():
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "canary audit-hook"}],
                },
                {
                    "matcher": "Write",
                    "hooks": [{"type": "command", "command": "canary audit-hook"}],
                },
                {
                    "matcher": "Edit",
                    "hooks": [{"type": "command", "command": "canary audit-hook"}],
                },
            ],
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": "canary watch-hook"}],
                }
            ],
        }
    }

    assert not _all_hooks_installed(settings)

    _install_hook(settings)

    assert _all_hooks_installed(settings)
    permission_hooks = settings["hooks"]["PermissionRequest"][0]["hooks"]
    prompt_hooks = settings["hooks"]["UserPromptSubmit"][0]["hooks"]

    assert {"type": "command", "command": "canary audit-hook"} in permission_hooks
    assert {"type": "command", "command": "canary prompt-hook"} in prompt_hooks


def test_bash_permission_allow_rules_filters_permissions_allow():
    settings = {
        "permissions": {
            "allow": [
                "Bash(git add *)",
                "Read(//tmp/**)",
                "Bash(npm install:*)",
                123,
            ]
        }
    }

    assert _bash_permission_allow_rules(settings) == [
        "Bash(git add *)",
        "Bash(npm install:*)",
    ]
