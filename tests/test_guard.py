from pathlib import Path

from canary.guard import guard_records, install_guard, remove_guard


def _make_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def test_install_guard_creates_shim_and_record(monkeypatch, tmp_path):
    real_bin_dir = tmp_path / "real-bin"
    shim_dir = tmp_path / "shim-bin"
    home_dir = tmp_path / "home"
    real_bin_dir.mkdir()
    shim_dir.mkdir()
    home_dir.mkdir()

    _make_executable(real_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    monkeypatch.setenv("PATH", str(real_bin_dir))
    monkeypatch.setattr("canary.guard.CONFIG_DIR", home_dir / ".canary")
    monkeypatch.setattr("canary.guard.CONFIG_PATH", home_dir / ".canary" / "guard.json")
    monkeypatch.setattr("canary.guard.DEFAULT_SHIM_DIR", shim_dir)

    record = install_guard("claude", watch=True, shim_dir=shim_dir)

    assert Path(record.shim_path).exists()
    assert record.real_binary == str(real_bin_dir / "claude")
    assert "canary.guard_shim" in Path(record.shim_path).read_text()

    records = guard_records()
    assert records["claude"].watch is True


def test_remove_guard_deletes_shim(monkeypatch, tmp_path):
    real_bin_dir = tmp_path / "real-bin"
    shim_dir = tmp_path / "shim-bin"
    home_dir = tmp_path / "home"
    real_bin_dir.mkdir()
    shim_dir.mkdir()
    home_dir.mkdir()

    _make_executable(real_bin_dir / "claude", "#!/usr/bin/env bash\nexit 0\n")

    monkeypatch.setenv("PATH", str(real_bin_dir))
    monkeypatch.setattr("canary.guard.CONFIG_DIR", home_dir / ".canary")
    monkeypatch.setattr("canary.guard.CONFIG_PATH", home_dir / ".canary" / "guard.json")
    monkeypatch.setattr("canary.guard.DEFAULT_SHIM_DIR", shim_dir)

    record = install_guard("claude", watch=False, shim_dir=shim_dir)
    assert Path(record.shim_path).exists()

    remove_guard("claude")

    assert not Path(record.shim_path).exists()
    assert "claude" not in guard_records()
