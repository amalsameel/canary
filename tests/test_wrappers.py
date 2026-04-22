from types import SimpleNamespace

import pytest

from canary.wrappers import _run_prompt_gate


def test_run_prompt_gate_allows_confirmed_risky_prompt(monkeypatch):
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")
    rendered = []
    logged = []

    monkeypatch.setattr("canary.wrappers.scan_prompt", lambda prompt: [finding])
    monkeypatch.setattr("canary.wrappers.semantic_scan", lambda prompt: [])
    monkeypatch.setattr("canary.wrappers.compute_risk_score", lambda findings: 80)
    monkeypatch.setattr("canary.wrappers.render_findings", lambda findings, score: rendered.append((findings, score)))
    monkeypatch.setattr("canary.wrappers.log_event", lambda *args, **kwargs: logged.append((args, kwargs)))
    monkeypatch.setattr("canary.wrappers._confirm", lambda prompt, default="n": True)

    _run_prompt_gate("fix auth", ".")

    assert rendered == [([finding], 80)]
    assert logged


def test_run_prompt_gate_blocks_declined_risky_prompt(monkeypatch):
    finding = SimpleNamespace(severity="HIGH", description="Credential handling")
    failures = []

    monkeypatch.setattr("canary.wrappers.scan_prompt", lambda prompt: [finding])
    monkeypatch.setattr("canary.wrappers.semantic_scan", lambda prompt: [])
    monkeypatch.setattr("canary.wrappers.compute_risk_score", lambda findings: 80)
    monkeypatch.setattr("canary.wrappers.render_findings", lambda findings, score: None)
    monkeypatch.setattr("canary.wrappers.log_event", lambda *args, **kwargs: None)
    monkeypatch.setattr("canary.wrappers._confirm", lambda prompt, default="n": False)
    monkeypatch.setattr("canary.wrappers.fail", lambda text, detail=None: failures.append((text, detail)))
    monkeypatch.setattr("canary.wrappers.console.print", lambda *args, **kwargs: None)

    with pytest.raises(SystemExit) as exc:
        _run_prompt_gate("fix auth", ".")

    assert exc.value.code == 1
    assert failures == [("blocked", "stopping before the agent receives the prompt")]
