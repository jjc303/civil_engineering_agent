from __future__ import annotations

import re
from typing import Any

import httpx
from pydantic import BaseModel, Field


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_FIELDS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,"
    "precipitation,weather_code,wind_speed_10m,wind_gusts_10m"
)


class WeatherLookupError(RuntimeError):
    """A location could not be resolved or the weather provider was unavailable."""


class CurrentWeather(BaseModel):
    location: str
    country: str | None = None
    observed_at: str
    temperature_c: float
    apparent_temperature_c: float | None = None
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100)
    precipitation_mm: float | None = Field(default=None, ge=0)
    wind_speed_kmh: float | None = Field(default=None, ge=0)
    wind_gusts_kmh: float | None = Field(default=None, ge=0)
    weather_code: int | None = None
    weather_summary: str


_WMO_SUMMARIES = {
    0: "晴朗",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴天",
    45: "有雾",
    48: "雾凇",
    51: "毛毛雨",
    53: "中等毛毛雨",
    55: "强毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨",
    81: "中等阵雨",
    82: "强阵雨",
    95: "雷暴",
    96: "伴冰雹雷暴",
    99: "强冰雹雷暴",
}

_WEATHER_KEYWORDS = ("天气", "气温", "温度", "降雨", "下雨", "风速")
_LOCATION_PREFIXES = ("请问", "帮我查询", "帮我查", "查询", "今天", "当前", "现在", "一下")


def extract_weather_location(question: str) -> str | None:
    """Extract an explicit location from a short Chinese/English weather question.

    This is intentionally deterministic: a weather question must never fall
    through to a safety-data tool solely because an LLM selected the wrong
    structured action.
    """
    keyword_match = re.search("|".join(_WEATHER_KEYWORDS), question, flags=re.IGNORECASE)
    if not keyword_match:
        return None
    candidate = question[:keyword_match.start()].strip(" ，。？?！!：:的 ")
    for prefix in _LOCATION_PREFIXES:
        if candidate.startswith(prefix):
            candidate = candidate[len(prefix):].strip(" ，。？?！!：:的 ")
    candidate = re.sub(r"^(?:帮忙)?(?:查一下|看一下)", "", candidate).strip()
    if 2 <= len(candidate) <= 128:
        return candidate
    return None


def get_current_weather(location: str, *, client: httpx.Client | None = None) -> CurrentWeather:
    """Resolve a human-readable location and fetch current conditions from Open-Meteo.

    The provider URLs and request parameters are fixed in code; LLM output only
    supplies a bounded location string and cannot choose an arbitrary URL.
    """
    normalized_location = location.strip()
    if not 2 <= len(normalized_location) <= 128:
        raise WeatherLookupError("weather location must contain 2 to 128 characters")

    owns_client = client is None
    http_client = client or httpx.Client(timeout=8.0, follow_redirects=False)
    try:
        geocode = http_client.get(
            GEOCODING_URL,
            params={"name": normalized_location, "count": 1, "language": "zh", "format": "json"},
        )
        geocode.raise_for_status()
        results = geocode.json().get("results") or []
        if not results:
            raise WeatherLookupError(f"weather location not found: {normalized_location}")

        place: dict[str, Any] = results[0]
        forecast = http_client.get(
            FORECAST_URL,
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": CURRENT_FIELDS,
                "timezone": "auto",
                "wind_speed_unit": "kmh",
            },
        )
        forecast.raise_for_status()
        current = forecast.json().get("current") or {}
        if "temperature_2m" not in current or "time" not in current:
            raise WeatherLookupError("weather provider returned no current conditions")

        code = current.get("weather_code")
        return CurrentWeather(
            location=place.get("name", normalized_location),
            country=place.get("country"),
            observed_at=current["time"],
            temperature_c=current["temperature_2m"],
            apparent_temperature_c=current.get("apparent_temperature"),
            relative_humidity_pct=current.get("relative_humidity_2m"),
            precipitation_mm=current.get("precipitation"),
            wind_speed_kmh=current.get("wind_speed_10m"),
            wind_gusts_kmh=current.get("wind_gusts_10m"),
            weather_code=code,
            weather_summary=_WMO_SUMMARIES.get(code, "天气状况未知"),
        )
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        raise WeatherLookupError("weather provider request failed") from exc
    finally:
        if owns_client:
            http_client.close()
