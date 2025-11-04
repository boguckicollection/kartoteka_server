import server


def test_uvicorn_config_uses_environment(monkeypatch):
    monkeypatch.setenv("HOST", "192.168.1.10")
    monkeypatch.setenv("PORT", "9000")
    monkeypatch.delenv("KARTOTEKA_HOST", raising=False)
    monkeypatch.delenv("KARTOTEKA_PORT", raising=False)
    monkeypatch.delenv("KARTOTEKA_RELOAD", raising=False)

    host, port, reload_enabled = server._uvicorn_config()

    assert host == "192.168.1.10"
    assert port == 9000
    assert reload_enabled is False


def test_uvicorn_config_handles_invalid_port(monkeypatch, caplog):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.setenv("KARTOTEKA_PORT", "not-a-number")

    with caplog.at_level("WARNING"):
        host, port, reload_enabled = server._uvicorn_config()

    assert host == "0.0.0.0"
    assert port == 8000
    assert reload_enabled is False
    assert "Invalid port value" in caplog.text


def test_uvicorn_config_respects_reload_flag(monkeypatch):
    monkeypatch.setenv("KARTOTEKA_RELOAD", "True")

    host, port, reload_enabled = server._uvicorn_config()

    assert host == "0.0.0.0"
    assert port == 8000
    assert reload_enabled is True
