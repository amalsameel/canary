# canary agent notes

This file used to contain the phased build prompt from the early scaffolding phase of the project. It no longer reflects the current repo and should not be treated as a source-of-truth implementation contract.

Use these files instead:

- `canary/cli.py`
  actual command surface and integration behavior
- `README.md`
  current user-facing install and usage guide
- `docs/README.md`
  concise user guide
- `docs/ARCH.md`
  current architecture overview
- `docs/CHANGELOG.md`
  historical session log

If you are updating Canary now:

1. Read the relevant source files directly.
2. Keep `README.md`, `docs/README.md`, and `canary/docs_topics.py` in sync with the CLI.
3. Treat `docs/CHANGELOG.md` as history, not as a requirements document.
4. Do not assume old docs about Codex support, wrapper scripts, or verbatim code-generation phases are still accurate.
