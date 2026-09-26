from __future__ import annotations

from typing import Any

import pytest

from agent.tools.weather import (
    CURRENT_FIELDS,
    FORECAST_URL,
    GEOCODING_URL,
    WeatherLookupError,
    get_current_weather,
    extract_weather_location,
)


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _WeatherClient:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, *, params: dict[str, Any]) -> _Response:
        self.calls.append((url, params))
        return self.responses.pop(0)


def test_get_current_weather_uses_fixed_open_meteo_endpoints() -> None:
    client = _WeatherClient([
        _Response({"results": [{"name": "北京市", "country": "中国", "latitude": 39.9042, "longitude": 116.4074}]}),
        _Response({"current": {
            "time": "2026-09-26T10:00",
            "temperature_2m": 22.4,
            "apparent_temperature": 21.8,
            "relative_humidity_2m": 64,
            "precipitation": 0.0,
            "weather_code": 2,
            "wind_speed_10m": 13.1,
            "wind_gusts_10m": 22.3,
        }}),
    ])

    weather = get_current_weather(" 北京 ", client=client)  # type: ignore[arg-type]

    assert weather.location == "北京市"
    assert weather.country == "中国"
    assert weather.weather_summary == "局部多云"
    assert weather.temperature_c == 22.4
    assert client.calls == [
        (GEOCODING_URL, {"name": "北京", "count": 1, "language": "zh", "format": "json"}),
        (FORECAST_URL, {
            "latitude": 39.9042,
            "longitude": 116.4074,
            "current": CURRENT_FIELDS,
            "timezone": "auto",
            "wind_speed_unit": "kmh",
        }),
    ]


@pytest.mark.parametrize(("question", "expected"), [
    ("长沙天气", "长沙"),
    ("请问今天长沙的天气怎么样？", "长沙"),
    ("上海浦东气温多少", "上海浦东"),
    ("今天有多少违规", None),
])
def test_extract_weather_location(question: str, expected: str | None) -> None:
    assert extract_weather_location(question) == expected


@pytest.mark.parametrize("location", ["", " ", "北", "x" * 129])
def test_get_current_weather_rejects_unbounded_locations(location: str) -> None:
    with pytest.raises(WeatherLookupError, match="2 to 128"):
        get_current_weather(location)
