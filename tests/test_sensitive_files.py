from canary.sensitive_files import is_sensitive


def test_env_file_sensitive():
    assert is_sensitive("/tmp/.env")
    assert is_sensitive("/tmp/.env.production")


def test_private_keys_sensitive():
    assert is_sensitive("/home/u/.ssh/id_rsa")
    assert is_sensitive("/home/u/.ssh/id_ed25519")
    assert is_sensitive("/tmp/server.key")
    assert is_sensitive("/tmp/cert.pem")


def test_normal_files_not_sensitive():
    assert not is_sensitive("/tmp/main.py")
    assert not is_sensitive("/tmp/README.md")
