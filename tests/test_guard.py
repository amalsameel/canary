from pathlib import Path

from canary.guard import default_shim_dir, get_enabled, guard_config_path, guard_records, install_guard, remove_guard, set_enabled


def _make_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def test_install_guard_creates_shim_and_record(monkeypatch, tmp_path):
    real_bin_dir = tmp_path / "real-bin"
    shim_dir = tmp_path / "shim-bin"
    real_bin_dir.mkdir()
    shim_dir.mkdir()

    _make_executable(real_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    monkeypatch.setenv("PATH", str(real_bin_dir))
    monkeypatch.setenv("CANARY_CONFIG_DIR", str(tmp_path / ".canary"))

    record = install_guard("claude", watch=True, shim_dir=shim_dir)

    assert Path(record.shim_path).exists()
    assert record.real_binary == str(real_bin_dir / "claude")
    assert "canary.guard_shim" in Path(record.shim_path).read_text()
    assert guard_config_path().exists()

    records = guard_records()
    assert records["claude"].watch is True


def test_remove_guard_deletes_shim(monkeypatch, tmp_path):
    real_bin_dir = tmp_path / "real-bin"
    shim_dir = tmp_path / "shim-bin"
    real_bin_dir.mkdir()
    shim_dir.mkdir()

    _make_executable(real_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    monkeypatch.setenv("PATH", str(real_bin_dir))
    monkeypatch.setenv("CANARY_CONFIG_DIR", str(tmp_path / ".canary"))

    record = install_guard("claude", watch=False, shim_dir=shim_dir)
    assert Path(record.shim_path).exists()

    remove_guard("claude")

    assert not Path(record.shim_path).exists()
    assert "claude" not in guard_records()


def test_guard_defaults_follow_canary_config_dir(monkeypatch, tmp_path):
    real_bin_dir = tmp_path / "real-bin"
    config_dir = tmp_path / ".canary"
    real_bin_dir.mkdir()

    _make_executable(real_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    monkeypatch.setenv("PATH", str(real_bin_dir))
    monkeypatch.setenv("CANARY_CONFIG_DIR", str(config_dir))

    record = install_guard("claude")

    assert Path(record.shim_path) == default_shim_dir() / "claude"
    assert guard_config_path() == config_dir / "guard.json"
    assert guard_config_path().exists()


def test_set_enabled_writes_guard_config_in_runtime_config_dir(monkeypatch, tmp_path):
    config_dir = tmp_path / ".canary"
    monkeypatch.setenv("CANARY_CONFIG_DIR", str(config_dir))

    set_enabled(False)

    assert get_enabled() is False
    assert guard_config_path() == config_dir / "guard.json"
    assert guard_config_path().exists()
