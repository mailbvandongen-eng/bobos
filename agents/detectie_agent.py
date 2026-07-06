"""Maak echt maandagadvies voor DetectieAgent op basis van Open-Meteo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from json_store import load_json, save_json_if_changed


ROOT_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT_DIR / "agents" / "detectie_rules.json"
OUTPUT_PATH = ROOT_DIR / "data" / "detectie.json"
DETECTIE_URL = "https://mailbvandongen-eng.github.io/detect/"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_DOCS_URL = "https://open-meteo.com/en/docs"
REFERENCE_LOCATION = {
    "label": "Midden-Nederland",
    "latitude": 52.09,
    "longitude": 5.12,
}
USER_AGENT = "BobOS DetectieAgent/0.3"

try:
    TIMEZONE = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:
    TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


@dataclass(frozen=True)
class DetectieContext:
    """Weercontext voor het maandagadvies."""

    week_condition: str
    rain_last_7_days_mm: float
    monday_date: date
    monday_precipitation_mm: float
    monday_temperature_max_c: float | None
    monday_wind_max_kmh: float | None


@dataclass(frozen=True)
class DetectieAdvice:
    """Compact terreinadvies voor de agenttegel en agentpagina."""

    status: str
    score: int
    best_choice: str
    avoid_choice: str
    tip: str
    details: list[str]
    context: DetectieContext


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_rules() -> list[dict[str, Any]]:
    """Lees de vaste detectieregels in."""
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("detectie_rules.json moet een lijst met regels bevatten.")

    return payload


def fetch_json(base_url: str, params: dict[str, Any]) -> dict[str, Any]:
    """Laad JSON van een externe bron."""
    query = urlencode(params, doseq=True)
    request = Request(
        f"{base_url}?{query}",
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=20) as response:
        return json.load(response)


def local_today() -> date:
    """Geef de lokale datum in Nederland terug."""
    return datetime.now(TIMEZONE).date()


def next_monday(from_date: date) -> date:
    """Bepaal de eerstvolgende maandag na de huidige datum."""
    days_ahead = (7 - from_date.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return from_date + timedelta(days=days_ahead)


def to_float(value: Any) -> float | None:
    """Converteer naar float als dat veilig kan."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_week_precipitation(today: date) -> float:
    """Lees de neerslagsom van de afgelopen zeven dagen uit Open-Meteo."""
    start_date = today - timedelta(days=6)
    payload = fetch_json(
        OPEN_METEO_URL,
        {
            "latitude": REFERENCE_LOCATION["latitude"],
            "longitude": REFERENCE_LOCATION["longitude"],
            "timezone": "Europe/Amsterdam",
            "daily": "precipitation_sum",
            "start_date": start_date.isoformat(),
            "end_date": today.isoformat(),
        },
    )

    daily = payload.get("daily") if isinstance(payload, dict) else {}
    values = daily.get("precipitation_sum") if isinstance(daily, dict) else []

    total = 0.0
    for value in values or []:
        number = to_float(value)
        if number is not None:
            total += number

    return round(total, 1)


def fetch_monday_forecast(target_date: date) -> dict[str, float | None]:
    """Lees de maandagverwachting uit Open-Meteo."""
    payload = fetch_json(
        OPEN_METEO_URL,
        {
            "latitude": REFERENCE_LOCATION["latitude"],
            "longitude": REFERENCE_LOCATION["longitude"],
            "timezone": "Europe/Amsterdam",
            "daily": [
                "precipitation_sum",
                "temperature_2m_max",
                "wind_speed_10m_max",
            ],
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
        },
    )

    daily = payload.get("daily") if isinstance(payload, dict) else {}

    def first_value(key: str) -> float | None:
        values = daily.get(key) if isinstance(daily, dict) else []
        if not values:
            return None
        return to_float(values[0])

    return {
        "precipitation_sum": first_value("precipitation_sum"),
        "temperature_2m_max": first_value("temperature_2m_max"),
        "wind_speed_10m_max": first_value("wind_speed_10m_max"),
    }


def detect_week_condition(rain_last_7_days_mm: float) -> str:
    """Vertaal neerslag naar een eenvoudige detectieconditie."""
    if rain_last_7_days_mm > 20:
        return "veel_regen"
    if rain_last_7_days_mm >= 10:
        return "natte_week"
    return "droge_week"


def rules_for_condition(
    rules: list[dict[str, Any]],
    condition: str,
    slot: str,
) -> list[dict[str, Any]]:
    """Filter regels op conditie en doelvak."""
    return [
        rule
        for rule in rules
        if str(rule.get("condition", "")).strip().lower() == condition
        and str(rule.get("slot", "")).strip().lower() == slot
    ]


def rule_advice(
    rules: list[dict[str, Any]],
    condition: str,
    slot: str,
    fallback: str,
) -> str:
    """Lees een enkel advies uit de regelset."""
    matches = rules_for_condition(rules, condition, slot)
    if not matches:
        return fallback

    return str(matches[0].get("advice", "")).strip() or fallback


def rule_score(rules: list[dict[str, Any]], condition: str, fallback: int) -> int:
    """Lees een score uit de regelset."""
    matches = rules_for_condition(rules, condition, "score")
    if not matches:
        return fallback

    try:
        return int(matches[0].get("value", fallback))
    except (TypeError, ValueError):
        return fallback


def rule_details(rules: list[dict[str, Any]], condition: str) -> list[str]:
    """Lees detailregels uit de regelset."""
    return [
        str(rule.get("advice", "")).strip()
        for rule in rules_for_condition(rules, condition, "detail")
        if str(rule.get("advice", "")).strip()
    ]


def build_weather_detail(context: DetectieContext) -> str:
    """Maak een compacte detailregel voor neerslag en maandagverwachting."""
    detail = (
        f"Afgelopen 7 dagen viel circa {context.rain_last_7_days_mm:.1f} mm regen. "
        f"Voor maandag {context.monday_date.isoformat()} wordt ongeveer "
        f"{context.monday_precipitation_mm:.1f} mm verwacht."
    )

    if context.monday_temperature_max_c is not None:
        detail += f" Verwachte maxtemp: {context.monday_temperature_max_c:.1f} C."

    return detail


def adjust_score_for_monday(score: int, monday_precipitation_mm: float) -> int:
    """Druk een score iets als maandag zelf erg nat oogt."""
    if monday_precipitation_mm >= 10:
        return max(1, score - 1)
    return score


def build_advice() -> DetectieAdvice:
    """Maak detectieadvies op basis van Open-Meteo en vaste kennisregels."""
    rules = load_rules()
    today = local_today()
    monday_date = next_monday(today)
    rain_last_7_days_mm = fetch_week_precipitation(today)
    monday_forecast = fetch_monday_forecast(monday_date)
    monday_precipitation_mm = monday_forecast.get("precipitation_sum") or 0.0

    context = DetectieContext(
        week_condition=detect_week_condition(rain_last_7_days_mm),
        rain_last_7_days_mm=rain_last_7_days_mm,
        monday_date=monday_date,
        monday_precipitation_mm=float(monday_precipitation_mm),
        monday_temperature_max_c=monday_forecast.get("temperature_2m_max"),
        monday_wind_max_kmh=monday_forecast.get("wind_speed_10m_max"),
    )

    score = rule_score(rules, context.week_condition, 3)
    score = adjust_score_for_monday(score, context.monday_precipitation_mm)
    details = rule_details(rules, context.week_condition)
    details.append(build_weather_detail(context))

    if context.monday_precipitation_mm >= 8:
        details.append(
            "Maandag oogt zelf ook nat; mik dan extra op hoger zand, droge ruggen en begaanbare oeverwallen."
        )
    elif context.monday_precipitation_mm <= 1.5:
        details.append(
            "Maandag lijkt relatief droog, waardoor hoge stroomruggen en droge oeverwallen extra aantrekkelijk worden."
        )

    return DetectieAdvice(
        status="Maandagadvies",
        score=score,
        best_choice=rule_advice(rules, context.week_condition, "best_choice", "Hoger zand / stroomrug"),
        avoid_choice=rule_advice(rules, context.week_condition, "avoid_choice", "Lage natte klei"),
        tip=rule_advice(rules, context.week_condition, "tip", "Kies het droogste terrein"),
        details=details,
        context=context,
    )


def build_fallback_payload(error: Exception) -> dict[str, Any]:
    """Maak een geldige fallback als de weerbron faalt."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Maandagadvies - bronfout",
        "score": 1,
        "items": [
            {"label": "Beste keuze", "value": "Later opnieuw laden"},
            {"label": "Vermijd", "value": "Blind varen op oude data"},
            {"label": "Tip", "value": "Controleer zondagavond opnieuw"},
        ],
        "details": [
            "Open-Meteo was tijdelijk niet bereikbaar, daarom is geen echt maandagadvies opgebouwd.",
            f"Foutmelding: {error}",
        ],
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Detectieregels", "note": "Lokaal kennisbestand"},
        ],
        "url": DETECTIE_URL,
    }


def build_payload(advice: DetectieAdvice) -> dict[str, Any]:
    """Maak de JSON-structuur voor DetectieAgent."""
    return {
        "updated_at": utc_now_iso(),
        "status": advice.status,
        "score": advice.score,
        "items": [
            {"label": "Beste keuze", "value": advice.best_choice},
            {"label": "Vermijd", "value": advice.avoid_choice},
            {"label": "Tip", "value": advice.tip},
        ],
        "details": advice.details,
        "context": {
            "reference_location": REFERENCE_LOCATION["label"],
            "rain_last_7_days_mm": advice.context.rain_last_7_days_mm,
            "week_condition": advice.context.week_condition,
            "monday_date": advice.context.monday_date.isoformat(),
            "monday_precipitation_mm": advice.context.monday_precipitation_mm,
            "monday_temperature_max_c": advice.context.monday_temperature_max_c,
            "monday_wind_max_kmh": advice.context.monday_wind_max_kmh,
        },
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Detectieregels", "note": "agents/detectie_rules.json"},
        ],
        "url": DETECTIE_URL,
    }


def save_payload(payload: dict[str, Any]) -> bool:
    """Schrijf het JSON-bestand alleen weg als de inhoud echt is gewijzigd."""
    return save_json_if_changed(OUTPUT_PATH, payload, ignored_keys={"updated_at"})


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    try:
        payload = build_payload(build_advice())
    except Exception as error:  # pragma: no cover
        current_payload = load_json(OUTPUT_PATH)
        if isinstance(current_payload, dict):
            print(
                f"[DONE] Open-Meteo onbereikbaar; bestaand {OUTPUT_PATH} blijft staan "
                "(ongewijzigd)."
            )
            return

        print(f"[WARN] DetectieAgent viel terug op fallback: {error}")
        payload = build_fallback_payload(error)

    changed = save_payload(payload)
    print(
        f"[DONE] Detectiedata gecontroleerd in {OUTPUT_PATH} "
        f"({'gewijzigd' if changed else 'ongewijzigd'})."
    )


if __name__ == "__main__":
    main()
