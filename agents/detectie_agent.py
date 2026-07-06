"""Maak praktisch detectieadvies met seizoen, regen en landschapstype."""

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
USER_AGENT = "BobOS DetectieAgent/0.4"
SEASON_LABELS = {
    "winter": "Winter",
    "lente": "Lente",
    "zomer": "Zomer",
    "herfst": "Herfst",
}

try:
    TIMEZONE = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:
    TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


@dataclass(frozen=True)
class DetectieProfile:
    """Profielscore voor een zoekperiode of materiaaltype."""

    name: str
    score: int
    advice: str


@dataclass(frozen=True)
class DetectieContext:
    """Weer- en seizoencontext voor detectieadvies."""

    season_key: str
    season_label: str
    field_access: str
    week_condition: str
    rain_last_7_days_mm: float | None
    monday_date: date
    monday_precipitation_mm: float | None
    monday_temperature_max_c: float | None
    monday_wind_max_kmh: float | None


@dataclass(frozen=True)
class DetectieAdvice:
    """Compact terreinadvies voor tegel en agentpagina."""

    status: str
    score: int
    best_choice: str
    avoid_choice: str
    tip: str
    details: list[str]
    profiles: list[DetectieProfile]
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


def detect_season(target_date: date) -> tuple[str, str]:
    """Bepaal het seizoen op basis van de huidige maand."""
    month = target_date.month
    if month in (12, 1, 2):
        return "winter", SEASON_LABELS["winter"]
    if month in (3, 4, 5):
        return "lente", SEASON_LABELS["lente"]
    if month in (6, 7, 8):
        return "zomer", SEASON_LABELS["zomer"]
    return "herfst", SEASON_LABELS["herfst"]


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
    slot: str | None = None,
) -> list[dict[str, Any]]:
    """Filter regels op conditie en optioneel op doelvak."""
    matches: list[dict[str, Any]] = []

    for rule in rules:
        if str(rule.get("condition", "")).strip().lower() != condition:
            continue

        if slot is not None and str(rule.get("slot", "")).strip().lower() != slot:
            continue

        matches.append(rule)

    return matches


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


def clamp_score(value: int) -> int:
    """Houd scores tussen 1 en 5."""
    return max(1, min(5, int(value)))


def season_score_delta(season_key: str) -> int:
    """Geef een lichte seizoenscorrectie voor algemene detectiekans."""
    adjustments = {
        "winter": 0,
        "lente": -1,
        "zomer": 0,
        "herfst": 1,
    }
    return adjustments.get(season_key, 0)


def condition_label(condition: str) -> str:
    """Maak een leesbaar label van de weekconditie."""
    labels = {
        "veel_regen": "Veel regen",
        "natte_week": "Natte week",
        "droge_week": "Droge week",
    }
    return labels.get(condition, "Onbekend")


def build_weather_detail(context: DetectieContext) -> str:
    """Maak een compacte detailregel voor neerslag en maandagverwachting."""
    if context.rain_last_7_days_mm is None:
        return (
            f"Afgelopen week: {condition_label(context.week_condition)}. "
            f"Maandagverwachting wordt opnieuw gevuld zodra Open-Meteo weer bereikbaar is."
        )

    detail = (
        f"Afgelopen 7 dagen viel circa {context.rain_last_7_days_mm:.1f} mm regen "
        f"({condition_label(context.week_condition).lower()}). "
        f"Voor maandag {context.monday_date.isoformat()} wordt ongeveer "
        f"{(context.monday_precipitation_mm or 0.0):.1f} mm verwacht."
    )

    if context.monday_temperature_max_c is not None:
        detail += f" Verwachte maxtemp: {context.monday_temperature_max_c:.1f} C."
    if context.monday_wind_max_kmh is not None:
        detail += f" Windpiek: {context.monday_wind_max_kmh:.0f} km/u."

    return detail


def monday_adjustment(monday_precipitation_mm: float | None) -> int:
    """Corrigeer de algemene score op basis van maandag zelf."""
    if monday_precipitation_mm is None:
        return 0
    if monday_precipitation_mm >= 10:
        return -1
    if monday_precipitation_mm <= 1.5:
        return 1
    return 0


def build_profile_score(
    profile_name: str,
    *,
    week_condition: str,
    season_key: str,
) -> int:
    """Bepaal een profielscore van 1 tot 5."""
    score = {
        "Steentijd": 3,
        "Romeins": 3,
        "Middeleeuws": 2,
    }.get(profile_name, 3)

    if profile_name == "Steentijd":
        if week_condition in {"natte_week", "veel_regen"}:
            score += 1
        if week_condition == "droge_week":
            score -= 1
        if season_key == "herfst":
            score += 1
        if season_key == "lente":
            score -= 1

    if profile_name == "Romeins":
        if week_condition in {"natte_week", "veel_regen"}:
            score += 1
        if season_key in {"herfst", "winter"}:
            score += 1
        if season_key == "lente":
            score -= 1

    if profile_name == "Middeleeuws":
        if season_key == "herfst":
            score += 2
        elif season_key == "winter":
            score += 1
        elif season_key == "lente":
            score -= 1
        if week_condition == "droge_week":
            score += 1

    return clamp_score(score)


def default_profile_advice(profile_name: str, week_condition: str) -> str:
    """Geef een veilige fallback voor profieladvies."""
    if profile_name == "Steentijd":
        if week_condition in {"natte_week", "veel_regen"}:
            return "Nat zand, dekzandruggen en rivierduinen zijn kansrijk."
        return "Hoger zand en vrijliggende ruggen zijn kansrijker dan drooggeslagen klei."

    if profile_name == "Romeins":
        return "Hoge stroomruggen en oude oeverwallen in rivierengebied blijven interessant."

    return "Akkers rond oude bewoning zijn pas echt interessant als ze geoogst of goed begaanbaar zijn."


def build_profiles(rules: list[dict[str, Any]], context: DetectieContext) -> list[DetectieProfile]:
    """Bouw drie compacte zoekprofielen op."""
    profiles: list[DetectieProfile] = []

    for profile_name, slot_name in (
        ("Steentijd", "profile_steentijd"),
        ("Romeins", "profile_romeins"),
        ("Middeleeuws", "profile_middeleeuws"),
    ):
        profiles.append(
            DetectieProfile(
                name=profile_name,
                score=build_profile_score(
                    profile_name,
                    week_condition=context.week_condition,
                    season_key=context.season_key,
                ),
                advice=rule_advice(
                    rules,
                    context.week_condition,
                    slot_name,
                    default_profile_advice(profile_name, context.week_condition),
                ),
            )
        )

    return profiles


def infer_week_condition_from_payload(payload: dict[str, Any]) -> str:
    """Leid een bruikbare weekconditie af uit oudere detectiedata."""
    haystack = " ".join(
        str(part)
        for part in [
            payload.get("status", ""),
            payload.get("details", ""),
            payload.get("items", ""),
        ]
    ).lower()

    if "steentijd op nat zand" in haystack or "regen" in haystack:
        return "natte_week"
    if "droge klei" in haystack or "stoppels" in haystack:
        return "droge_week"

    score = payload.get("score")
    if isinstance(score, (int, float)) and score <= 2:
        return "veel_regen"
    return "natte_week"


def payload_has_profiles(payload: Any) -> bool:
    """Controleer of detectiedata al het uitgebreidere profielblok bevat."""
    if not isinstance(payload, dict):
        return False

    profiles = payload.get("profiles")
    return isinstance(profiles, list) and len(profiles) >= 3


def migrate_existing_payload(payload: Any) -> dict[str, Any] | None:
    """Verrijk oudere detectiedata als live weerdata tijdelijk ontbreekt."""
    if not isinstance(payload, dict):
        return None

    rules = load_rules()
    today = local_today()
    monday_date = next_monday(today)
    season_key, season_label = detect_season(today)
    week_condition = infer_week_condition_from_payload(payload)

    context = DetectieContext(
        season_key=season_key,
        season_label=season_label,
        field_access=rule_advice(
            rules,
            f"season_{season_key}",
            "field_access",
            "Kies vooral percelen die vrij, geoogst of zichtbaar geroerd zijn.",
        ),
        week_condition=week_condition,
        rain_last_7_days_mm=None,
        monday_date=monday_date,
        monday_precipitation_mm=None,
        monday_temperature_max_c=None,
        monday_wind_max_kmh=None,
    )

    existing_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    item_map = {
        str(item.get("label", "")).strip(): str(item.get("value", "")).strip()
        for item in existing_items
        if isinstance(item, dict)
    }

    best_choice = item_map.get(
        "Beste keuze",
        rule_advice(rules, week_condition, "best_choice", "Hoger zand / stroomrug"),
    )
    avoid_choice = item_map.get(
        "Vermijd",
        rule_advice(rules, week_condition, "avoid_choice", "Lage natte klei"),
    )
    tip = item_map.get(
        "Tip",
        rule_advice(rules, week_condition, "tip", "Kijk naar het droogste bereikbare terrein"),
    )

    details = rule_details(rules, f"season_{season_key}")
    details.extend(rule_details(rules, week_condition))
    details.extend(
        [
            build_weather_detail(context),
            f"Beste landschapstype nu: {best_choice}.",
            f"Vermijden: {avoid_choice}.",
        ]
    )

    score = clamp_score(
        int(payload.get("score", rule_score(rules, week_condition, 3))) + season_score_delta(season_key)
    )
    profiles = build_profiles(rules, context)

    return build_payload(
        DetectieAdvice(
            status="Maandagadvies",
            score=score,
            best_choice=best_choice,
            avoid_choice=avoid_choice,
            tip=tip,
            details=details,
            profiles=profiles,
            context=context,
        )
    )


def build_advice() -> DetectieAdvice:
    """Maak detectieadvies op basis van Open-Meteo en vaste kennisregels."""
    rules = load_rules()
    today = local_today()
    monday_date = next_monday(today)
    season_key, season_label = detect_season(today)
    rain_last_7_days_mm = fetch_week_precipitation(today)
    monday_forecast = fetch_monday_forecast(monday_date)
    week_condition = detect_week_condition(rain_last_7_days_mm)

    context = DetectieContext(
        season_key=season_key,
        season_label=season_label,
        field_access=rule_advice(
            rules,
            f"season_{season_key}",
            "field_access",
            "Kies vooral percelen die vrij, geoogst of zichtbaar geroerd zijn.",
        ),
        week_condition=week_condition,
        rain_last_7_days_mm=rain_last_7_days_mm,
        monday_date=monday_date,
        monday_precipitation_mm=monday_forecast.get("precipitation_sum"),
        monday_temperature_max_c=monday_forecast.get("temperature_2m_max"),
        monday_wind_max_kmh=monday_forecast.get("wind_speed_10m_max"),
    )

    best_choice = rule_advice(rules, week_condition, "best_choice", "Hoger zand / stroomrug")
    avoid_choice = rule_advice(rules, week_condition, "avoid_choice", "Lage natte klei")
    tip = rule_advice(rules, week_condition, "tip", "Kies het droogste terrein")

    score = rule_score(rules, week_condition, 3)
    score += season_score_delta(season_key)
    score += monday_adjustment(context.monday_precipitation_mm)
    score = clamp_score(score)

    details = rule_details(rules, f"season_{season_key}")
    details.extend(rule_details(rules, week_condition))
    details.append(f"{season_label}: {context.field_access}")
    details.append(build_weather_detail(context))
    details.append(f"Beste landschapstype nu: {best_choice}.")
    details.append(f"Vermijden: {avoid_choice}.")
    details.append("Betuwe niet uitsluiten: hoge stroomruggen en oude oeverwallen blijven interessant als ze hoog en droog genoeg zijn.")

    if context.monday_precipitation_mm is not None and context.monday_precipitation_mm >= 8:
        details.append(
            "Maandag oogt zelf ook nat; mik dan extra op hoger zand, droge ruggen en begaanbare oeverwallen."
        )
    elif context.monday_precipitation_mm is not None and context.monday_precipitation_mm <= 1.5:
        details.append(
            "Maandag lijkt relatief droog, waardoor hoge stroomruggen en droge oeverwallen extra aantrekkelijk worden."
        )

    profiles = build_profiles(rules, context)

    if season_key == "zomer":
        tip = f"{tip}; focus ook op net geoogste graanpercelen zodra ze beschikbaar komen."
    elif season_key == "lente":
        tip = f"{tip}; vermijd ingezaaide velden en jonge gewassen."

    return DetectieAdvice(
        status="Maandagadvies",
        score=score,
        best_choice=best_choice,
        avoid_choice=avoid_choice,
        tip=tip,
        details=details,
        profiles=profiles,
        context=context,
    )


def build_fallback_payload(error: Exception) -> dict[str, Any]:
    """Maak een geldige fallback als er nog geen detectiedata bestaat."""
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
        "profiles": [
            {"name": "Steentijd", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
            {"name": "Romeins", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
            {"name": "Middeleeuws", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
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
        "profiles": [
            {
                "name": profile.name,
                "score": profile.score,
                "advice": profile.advice,
            }
            for profile in advice.profiles
        ],
        "context": {
            "reference_location": REFERENCE_LOCATION["label"],
            "season": advice.context.season_key,
            "season_label": advice.context.season_label,
            "field_access": advice.context.field_access,
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
        if current_payload is not None:
            migrated_payload = migrate_existing_payload(current_payload)
            if migrated_payload is not None:
                changed = save_payload(migrated_payload)
                print(
                    f"[DONE] Bestaande detectiedata bijgewerkt in {OUTPUT_PATH} "
                    f"({'gewijzigd' if changed else 'ongewijzigd'})."
                )
                return

            if payload_has_profiles(current_payload):
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
