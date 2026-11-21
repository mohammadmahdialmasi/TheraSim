from app.core import hardware


def test_hardware_assessment_handles_missing_optional_resources(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(hardware, "_memory_bytes", lambda: (None, None))
    monkeypatch.setattr(
        hardware,
        "_detect_nvidia_gpus",
        lambda: ([], "not_detected"),
    )
    monkeypatch.setattr(hardware.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        hardware,
        "_probe_ollama",
        lambda base_url: {
            "server_available": False,
            "server_version": None,
            "server_status": "unavailable",
        },
    )

    result = hardware.assess_hardware(data_directory=tmp_path)

    assert result["memory"] == {
        "total_bytes": None,
        "available_bytes": None,
    }
    assert result["gpus"] == []
    assert result["ollama"]["cli_available"] is False
    assert result["disk"]["scope"] == "application data volume"
    assert "must be verified" in result["recommendation_status"]


def test_remote_ollama_hardware_probe_is_never_attempted(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("Remote endpoint must not be probed.")

    monkeypatch.setattr(hardware.httpx, "get", fail_if_called)

    result = hardware._probe_ollama("https://provider.example:443")

    assert result["server_available"] is None
    assert result["server_status"] == (
        "not_probed_non_loopback_or_invalid_endpoint"
    )


def test_loopback_ollama_probe_reports_service_version(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"version": "0.34.4"}

    def fake_get(url, timeout):
        assert url == "http://127.0.0.1:11434/api/version"
        assert timeout == 0.75
        return Response()

    monkeypatch.setattr(hardware.httpx, "get", fake_get)

    result = hardware._probe_ollama("http://127.0.0.1:11434/v1")

    assert result == {
        "server_available": True,
        "server_version": "0.34.4",
        "server_status": "available",
    }
