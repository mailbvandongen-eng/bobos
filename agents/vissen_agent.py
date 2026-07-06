"""Maak echt visadvies voor vandaag en vanavond met Open-Meteo."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from json_store import load_json, save_json_if_changed


ROOT_DIR = Path(__file__).resolve().parent.parent
RULES_PATH = ROOT_DIR / "agents" / "vissen_rules.json"
OUTPUT_PATH = ROOT_DIR / "data" / "vissen.json"
VISSEN_URL = "https://mailbvandongen-eng.github.io/visapp/"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_DOCS_URL = "https://open-meteo.com/en/docs"
REFERENCE_LOCATION = {
    "label": "Midden-Nederland",
    "latitude": 52.09,
    "longitude": 5.12,
}
USER_AGENT = "BobOS VisAgent/0.3"

try:
    TIMEZONE = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:
    TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


@dataclass(frozen=True)
class WeatherPoint:
    """Enkel weerdatapunt voor de visanalyse."""

    timestamp: datetime
    wind_speed_kmh: float
    pressure_hpa: float
    temperature_c: float
    precipitation_mm: float


@dataclass(frozen=True)
class VisAdvice:
    """Compact visadvies voor tegel en agentpagina."""

    status: str
    score: int
    wind_value: str
    pressure_value: str
    best_time: str
    tip: str
    details: list[str]
    context: dict[str, Any]


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_rules() -> list[dict[str, Any]]:
    """Lees de visregels in."""
    with RULES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("vissen_rules.json moet een lijst met regels bevatten.")

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


def local_now() -> datetime:
    """Geef de huidige lokale tijd terug."""
    return datetime.now(TIMEZONE)


def to_float(value: Any) -> float | None:
    """Converteer veilig naar float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_weather_points(target_date: date) -> list[WeatherPoint]:
    """Lees uurlijkse weerdata voor vandaag uit Open-Meteo."""
    payload = fetch_json(
        OPEN_METEO_URL,
        {
            "latitude": REFERENCE_LOCATION["latitude"],
            "longitude": REFERENCE_LOCATION["longitude"],
            "timezone": "Europe/Amsterdam",
            "wind_speed_unit": "kmh",
            "hourly": [
                "wind_speed_10m",
                "pressure_msl",
                "temperature_2m",
                "precipitation",
            ],
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
        },
    )

    hourly = payload.get("hourly") if isinstance(payload, dict) else {}
    times = hourly.get("time") if isinstance(hourly, dict) else []
    wind_values = hourly.get("wind_speed_10m") if isinstance(hourly, dict) else []
    pressure_values = hourly.get("pressure_msl") if isinstance(hourly, dict) else []
    temperature_values = hourly.get("temperature_2m") if isinstance(hourly, dict) else []
    precipitation_values = hourly.get("precipitation") if isinstance(hourly, dict) else []

    points: list[WeatherPoint] = []
    for raw_time, raw_wind, raw_pressure, raw_temp, raw_precip in zip(
        times or [],
        wind_values or [],
        pressure_values or [],
        temperature_values or [],
        precipitation_values or [],
    ):
        wind_speed_kmh = to_float(raw_wind)
        pressure_hpa = to_float(raw_pressure)
        temperature_c = to_float(raw_temp)
        precipitation_mm = to_float(raw_precip)

        if None in (wind_speed_kmh, pressure_hpa, temperature_c, precipitation_mm):
            continue

        try:
            timestamp = datetime.fromisoformat(str(raw_time))
        except ValueError:
            continue

        points.append(
            WeatherPoint(
                timestamp=timestamp.replace(tzinfo=TIMEZONE),
                wind_speed_kmh=float(wind_speed_kmh),
                pressure_hpa=float(pressure_hpa),
                temperature_c=float(temperature_c),
                precipitation_mm=float(precipitation_mm),
            )
        )

    return points


def points_between(
    points: list[WeatherPoint],
    start_hour: int,
    end_hour: int,
    *,
    after: datetime | None = None,
) -> list[WeatherPoint]:
    """Filter punten op lokaal uurvenster."""
    selected: list[WeatherPoint] = []

    for point in points:
        local_point = point.timestamp.astimezone(TIMEZONE)
        point_time = local_point.timetz().replace(tzinfo=None)
        if point_time < time(start_hour) or point_time > time(end_hour):
            continue
        if after is not None and local_point < after:
            continue
        selected.append(point)

    return selected


def average_value(points: list[WeatherPoint], field_name: str) -> float | None:
    """Bepaal het gemiddelde van een veld over meerdere punten."""
    values = [getattr(point, field_name) for point in points]
    if not values:
        return None
    return float(mean(values))


def total_precipitation(points: list[WeatherPoint]) -> float:
    """Tel neerslag in een puntreeks op."""
    return round(sum(point.precipitation_mm for point in points), 1)


def wind_condition(wind_speed_kmh: float) -> str:
    """Vertaal windsnelheid naar een eenvoudige conditie."""
    if wind_speed_kmh < 10:
        return "lage_wind"
    if wind_speed_kmh <= 25:
        return "matige_wind"
    return "harde_wind"


def pressure_condition(delta_hpa: float) -> str:
    """Vertaal drukverandering naar een eenvoudige conditie."""
    if delta_hpa <= -2:
        return "dalende_druk"
    if delta_hpa >= 2:
        return "stijgende_druk"
    return "stabiele_druk"


def precipitation_condition(evening_precip_mm: float) -> str:
    """Vertaal avondneerslag naar een conditie."""
    if evening_precip_mm > 4:
        return "natte_avond"
    return "droge_avond"


def temperature_condition(evening_temperature_c: float) -> str:
    """Vertaal avondtemperatuur naar een conditie."""
    if evening_temperature_c >= 18:
        return "warme_avond"
    return "koele_avond"


def bft_from_kmh(wind_speed_kmh: float) -> int:
    """Zet km/u grof om naar Beaufort."""
    thresholds = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
    for index, threshold in enumerate(thresholds):
        if wind_speed_kmh <= threshold:
            return index
    return 12


def find_rule(
    rules: list[dict[str, Any]],
    condition: str,
    slot: str,
) -> str | None:
    """Lees de eerste passende regeltekst."""
    for rule in rules:
        if str(rule.get("condition", "")).strip().lower() != condition:
            continue
        if str(rule.get("slot", "")).strip().lower() != slot:
            continue

        advice = str(rule.get("advice", "")).strip()
        if advice:
            return advice

    return None


def build_tip(
    rules: list[dict[str, Any]],
    conditions: list[str],
    score: int,
) -> str:
    """Bepaal de hoofdtip voor de visdag."""
    for condition in conditions:
        advice = find_rule(rules, condition, "tip")
        if advice:
            return advice

    if score >= 4:
        return "Roofvis en meerval kansrijk rond schemer."

    return "Algemene viskans redelijk; focus op de overgang naar schemer."


def best_time_label(
    now: datetime,
    afternoon_points: list[WeatherPoint],
    evening_points: list[WeatherPoint],
) -> str:
    """Kies het beste vismoment voor later vandaag."""
    afternoon_precip = total_precipitation(afternoon_points)
    evening_precip = total_precipitation(evening_points)
    evening_wind = average_value(evening_points, "wind_speed_kmh") or 0.0

    if evening_points and evening_precip <= 1.5 and evening_wind <= 25:
        return "Avond"

    if afternoon_points and afternoon_precip <= 1.5 and now.hour < 18:
        return "Late middag"

    return "Kort droog venster"


def build_details(
    rules: list[dict[str, Any]],
    conditions: list[str],
    *,
    evening_precip_mm: float,
    pressure_delta_hpa: float,
) -> list[str]:
    """Maak compacte analyse-regels voor de agentpagina."""
    details: list[str] = []

    for condition in conditions:
        advice = find_rule(rules, condition, "detail")
        if advice and advice not in details:
            details.append(advice)

    details.append(
        f"Vanmiddag naar vanavond wordt circa {evening_precip_mm:.1f} mm neerslag verwacht; "
        f"drukverandering over de dag: {pressure_delta_hpa:+.1f} hPa."
    )

    return details


def build_score(
    wind_state: str,
    pressure_state: str,
    rain_state: str,
    temp_state: str,
) -> int:
    """Bepaal een eenvoudige visscore van 1 tot 5."""
    score = 2

    if wind_state == "matige_wind":
        score += 1
    elif wind_state == "harde_wind":
        score -= 1

    if pressure_state == "dalende_druk":
        score += 1
    elif pressure_state == "stabiele_druk":
        score += 1

    if rain_state == "droge_avond":
        score += 1
    else:
        score -= 1

    if temp_state == "warme_avond":
        score += 0

    return max(1, min(5, score))


def build_advice() -> VisAdvice:
    """Maak visadvies op basis van Open-Meteo en vaste regels."""
    rules = load_rules()
    now = local_now()
    today = now.date()
    points = fetch_weather_points(today)

    if not points:
        raise RuntimeError("Geen uurlijkse weerdata ontvangen van Open-Meteo.")

    afternoon_points = points_between(points, 14, 18, after=now)
    evening_points = points_between(points, 18, 23, after=now)
    active_window = evening_points or afternoon_points or points

    wind_avg_kmh = average_value(active_window, "wind_speed_kmh") or 0.0
    pressure_avg_hpa = average_value(active_window, "pressure_hpa") or 0.0
    evening_temperature_c = average_value(evening_points or active_window, "temperature_c") or 0.0
    evening_precip_mm = total_precipitation(evening_points or active_window)

    early_points = points_between(points, 6, 12)
    late_points = points_between(points, 18, 23)
    early_pressure = average_value(early_points or points, "pressure_hpa") or pressure_avg_hpa
    late_pressure = average_value(late_points or active_window, "pressure_hpa") or pressure_avg_hpa
    pressure_delta_hpa = round(late_pressure - early_pressure, 1)

    wind_state = wind_condition(wind_avg_kmh)
    pressure_state = pressure_condition(pressure_delta_hpa)
    rain_state = precipitation_condition(evening_precip_mm)
    temp_state = temperature_condition(evening_temperature_c)
    conditions = [wind_state, pressure_state, rain_state, temp_state]

    score = build_score(wind_state, pressure_state, rain_state, temp_state)
    best_time = best_time_label(now, afternoon_points, evening_points)
    tip = build_tip(
        rules,
        [rain_state, wind_state, temp_state, pressure_state],
        score,
    )
    details = build_details(
        rules,
        [wind_state, pressure_state, rain_state],
        evening_precip_mm=evening_precip_mm,
        pressure_delta_hpa=pressure_delta_hpa,
    )

    return VisAdvice(
        status="Viscondities vandaag",
        score=score,
        wind_value=f"{wind_avg_kmh:.0f} km/u ({bft_from_kmh(wind_avg_kmh)} Bft)",
        pressure_value=f"{pressure_avg_hpa:.0f} hPa ({pressure_state.replace('_', ' ')})",
        best_time=best_time,
        tip=tip,
        details=details,
        context={
            "reference_location": REFERENCE_LOCATION["label"],
            "wind_avg_kmh": round(wind_avg_kmh, 1),
            "pressure_avg_hpa": round(pressure_avg_hpa, 1),
            "pressure_delta_hpa": pressure_delta_hpa,
            "evening_temperature_c": round(evening_temperature_c, 1),
            "evening_precipitation_mm": evening_precip_mm,
            "conditions": conditions,
        },
    )


def build_fallback_payload(error: Exception) -> dict[str, Any]:
    """Maak een geldige fallback als de weerbron faalt."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Viscondities vandaag - bronfout",
        "score": 1,
        "items": [
            {"label": "Wind", "value": "Onbekend"},
            {"label": "Luchtdruk", "value": "Onbekend"},
            {"label": "Beste tijd", "value": "Later opnieuw laden"},
            {"label": "Tip", "value": "Controleer de bron later opnieuw"},
        ],
        "details": [
            "Open-Meteo was tijdelijk niet bereikbaar, daarom is geen echt visadvies opgebouwd.",
            f"Foutmelding: {error}",
        ],
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Visregels", "note": "Lokaal kennisbestand"},
        ],
        "url": VISSEN_URL,
    }


def build_payload(advice: VisAdvice) -> dict[str, Any]:
    """Maak de JSON-structuur voor VisAgent."""
    return {
        "updated_at": utc_now_iso(),
        "status": advice.status,
        "score": advice.score,
        "items": [
            {"label": "Wind", "value": advice.wind_value},
            {"label": "Luchtdruk", "value": advice.pressure_value},
            {"label": "Beste tijd", "value": advice.best_time},
            {"label": "Tip", "value": advice.tip},
        ],
        "details": advice.details,
        "context": advice.context,
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Visregels", "note": "agents/vissen_rules.json"},
        ],
        "url": VISSEN_URL,
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

        print(f"[WARN] VisAgent viel terug op fallback: {error}")
        payload = build_fallback_payload(error)

    changed = save_payload(payload)
    print(
        f"[DONE] Visdata gecontroleerd in {OUTPUT_PATH} "
        f"({'gewijzigd' if changed else 'ongewijzigd'})."
    )


if __name__ == "__main__":
    main()
