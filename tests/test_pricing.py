import datetime as dt

from kartoteka import pricing


class DummyResponse:
    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {"rates": [{"mid": 4.5}]}

    def json(self) -> dict:
        return self._payload


def _reset_exchange_cache() -> None:
    pricing._exchange_rate_cache["value"] = None
    pricing._exchange_rate_cache["date"] = None


def test_get_exchange_rate_uses_cache(monkeypatch):
    _reset_exchange_cache()

    monkeypatch.setattr(pricing, "_current_date", lambda: dt.date(2024, 1, 1))

    def fake_get(_url, timeout=None, **_kwargs):
        return DummyResponse(payload={"rates": [{"mid": 4.5}]})

    monkeypatch.setattr(pricing.requests, "get", fake_get)

    first = pricing.get_exchange_rate()
    assert first == 4.5

    def fail_get(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("Unexpected HTTP request")

    monkeypatch.setattr(pricing.requests, "get", fail_get)

    second = pricing.get_exchange_rate()
    assert second == 4.5


def test_get_exchange_rate_refreshes_each_day(monkeypatch):
    _reset_exchange_cache()

    payloads = iter([
        {"rates": [{"mid": 4.5}]},
        {"rates": [{"mid": 4.7}]},
    ])

    def fake_get(_url, timeout=None, **_kwargs):
        return DummyResponse(payload=next(payloads))

    current_day = {"value": dt.date(2024, 1, 1)}

    def fake_today():
        return current_day["value"]

    monkeypatch.setattr(pricing, "_current_date", fake_today)
    monkeypatch.setattr(pricing.requests, "get", fake_get)

    initial = pricing.get_exchange_rate()
    assert initial == 4.5

    current_day["value"] = dt.date(2024, 1, 2)
    refreshed = pricing.get_exchange_rate()
    assert refreshed == 4.7
