"""Maak praktisch visadvies voor vandaag op basis van weer, trend en seizoen."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
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
WATERINFO_API_BASE = "https://waterinfo.rws.nl/api"
WATERINFO_TIDE_VIEW_URL = "https://waterinfo.rws.nl/publiek/astronomische-getij/"
TIDE_REFERENCE_STATION = {
    "label": "IJmuiden, buitenhaven",
    "location_code": "ijmuiden.buitenhaven",
}
REFERENCE_LOCATION = {
    "label": "Midden-Nederland",
    "latitude": 52.09,
    "longitude": 5.12,
}
USER_AGENT = "BobOS VisAgent/0.4"
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
class WeatherPoint:
    """Enkel weerdatapunt voor de visanalyse."""

    timestamp: datetime
    wind_speed_kmh: float
    wind_direction_deg: float
    pressure_hpa: float
    temperature_c: float
    precipitation_mm: float
    cape_j_kg: float


@dataclass(frozen=True)
class TidePoint:
    """Enkel getijdedatapunt voor zoutwateradvies."""

    timestamp: datetime
    level_cm: float


@dataclass(frozen=True)
class TideExtreme:
    """Gedetecteerd hoog- of laagwatermoment."""

    kind: str
    timestamp: datetime
    level_cm: float


@dataclass(frozen=True)
class TideSummary:
    """Samenvatting van de eerstvolgende getijmomenten."""

    location_label: str
    location_code: str
    reference_plane: str
    timezone_identifier: str
    range_value: str
    current_level_cm: float | None
    next_extreme: TideExtreme | None
    following_extreme: TideExtreme | None
    amplitude_cm: float
    active_window_label: str | None


@dataclass(frozen=True)
class VisProfile:
    """Profielscore voor type visserij."""

    name: str
    score: int
    advice: str


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
    profiles: list[VisProfile]
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


def parse_api_timestamp(value: str) -> datetime:
    """Zet een API-tijd veilig om naar een timezone-aware datetime."""
    cleaned = str(value).strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    return datetime.fromisoformat(cleaned).astimezone(TIMEZONE)


def format_local_timestamp(value: datetime | None) -> str:
    """Formatteer lokale datum+tijd compact voor adviesregels."""
    if value is None:
        return "onbekend"
    return value.astimezone(TIMEZONE).strftime("%a %H:%M").replace("Mon", "ma").replace("Tue", "di").replace("Wed", "wo").replace("Thu", "do").replace("Fri", "vr").replace("Sat", "za").replace("Sun", "zo")


def fetch_tide_detail(location_code: str) -> dict[str, Any]:
    """Lees detailinformatie van de publieke Waterinfo getijviewer."""
    return fetch_json(
        f"{WATERINFO_API_BASE}/detail/get",
        {
            "locationCode": location_code,
            "mapType": "astronomische-getij",
        },
    )


def select_tide_range_value(detail: dict[str, Any]) -> str:
    """Pak bij voorkeur de 24-uurs voorspelling uit de range-opties."""
    ranges = detail.get("range")
    if isinstance(ranges, list):
        for item in ranges:
            if not isinstance(item, dict):
                continue
            if str(item.get("label", "")).strip().lower() == "1 dag vooruit":
                value = str(item.get("value", "")).strip()
                if value:
                    return value
        for item in ranges:
            value = str(item.get("value", "")).strip()
            if value.startswith("0,"):
                return value
    return "0,24"


def fetch_tide_points(
    *,
    location_code: str,
    range_value: str,
    reference_plane: str,
    timezone_identifier: str,
) -> list[TidePoint]:
    """Lees een 24-uurs getijcurve op uit Waterinfo."""
    payload = fetch_json(
        f"{WATERINFO_API_BASE}/chart/get",
        {
            "mapType": "astronomische-getij",
            "locationCodes": [location_code],
            "values": range_value,
            "getijReference": reference_plane,
            "timeZone": timezone_identifier,
        },
    )
    series = payload.get("series") if isinstance(payload, dict) else None
    if not isinstance(series, list) or not series:
        return []

    data = series[0].get("data") if isinstance(series[0], dict) else None
    if not isinstance(data, list):
        return []

    points: list[TidePoint] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        timestamp_raw = item.get("dateTime")
        level_cm = to_float(item.get("value"))
        if level_cm is None or not timestamp_raw:
            continue
        try:
            timestamp = parse_api_timestamp(str(timestamp_raw))
        except ValueError:
            continue
        points.append(TidePoint(timestamp=timestamp, level_cm=float(level_cm)))

    return points


def detect_tide_extremes(points: list[TidePoint]) -> list[TideExtreme]:
    """Zoek eenvoudige hoog- en laagwatermomenten uit een tijreeks."""
    if len(points) < 3:
        return []

    extremes: list[TideExtreme] = []
    previous_sign: int | None = None

    for index in range(1, len(points)):
        delta = points[index].level_cm - points[index - 1].level_cm
        sign = 1 if delta > 0 else -1 if delta < 0 else 0
        if sign == 0:
            continue
        if previous_sign is None:
            previous_sign = sign
            continue
        if sign == previous_sign:
            continue

        turning_point = points[index - 1]
        kind = "hoogwater" if previous_sign > 0 and sign < 0 else "laagwater"
        if not extremes or extremes[-1].timestamp != turning_point.timestamp:
            extremes.append(
                TideExtreme(
                    kind=kind,
                    timestamp=turning_point.timestamp,
                    level_cm=turning_point.level_cm,
                )
            )
        previous_sign = sign

    return extremes


def build_tide_window_label(extreme: TideExtreme | None) -> str | None:
    """Omschrijf het beste venster rond een kentering compact."""
    if extreme is None:
        return None
    start = extreme.timestamp - timedelta(hours=1, minutes=30)
    end = extreme.timestamp + timedelta(hours=1)
    return (
        f"{start.astimezone(TIMEZONE).strftime('%H:%M')}-"
        f"{end.astimezone(TIMEZONE).strftime('%H:%M')} rond {extreme.kind}"
    )


def build_tide_summary(now: datetime) -> TideSummary:
    """Bouw een compacte samenvatting uit publieke Waterinfo-getijdata."""
    detail = fetch_tide_detail(TIDE_REFERENCE_STATION["location_code"])
    getij = detail.get("getij") if isinstance(detail, dict) else {}
    default_reference = "NAP"
    if isinstance(getij, dict):
        default_reference = str(getij.get("defaultReferencePlane", "NAP")).strip() or "NAP"

    timezone_identifier = "GMT"
    if isinstance(getij, dict):
        timezones = getij.get("timezones")
        if isinstance(timezones, list) and timezones:
            first_timezone = timezones[0]
            if isinstance(first_timezone, dict):
                timezone_identifier = str(first_timezone.get("identifier", "GMT")).strip() or "GMT"

    range_value = select_tide_range_value(detail)
    location_label = str(detail.get("location", TIDE_REFERENCE_STATION["label"])).strip() or TIDE_REFERENCE_STATION["label"]
    points = fetch_tide_points(
        location_code=TIDE_REFERENCE_STATION["location_code"],
        range_value=range_value,
        reference_plane=default_reference,
        timezone_identifier=timezone_identifier,
    )

    if not points:
        raise RuntimeError("Waterinfo gaf geen getijpunten terug.")

    current_level_cm = points[0].level_cm
    amplitude_cm = round(max(point.level_cm for point in points) - min(point.level_cm for point in points), 1)
    upcoming_extremes = [extreme for extreme in detect_tide_extremes(points) if extreme.timestamp >= now]

    next_extreme = upcoming_extremes[0] if upcoming_extremes else None
    following_extreme = upcoming_extremes[1] if len(upcoming_extremes) > 1 else None

    return TideSummary(
        location_label=location_label,
        location_code=TIDE_REFERENCE_STATION["location_code"],
        reference_plane=default_reference,
        timezone_identifier=timezone_identifier,
        range_value=range_value,
        current_level_cm=current_level_cm,
        next_extreme=next_extreme,
        following_extreme=following_extreme,
        amplitude_cm=amplitude_cm,
        active_window_label=build_tide_window_label(next_extreme),
    )


def local_now() -> datetime:
    """Geef de huidige lokale tijd terug."""
    return datetime.now(TIMEZONE)


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
    """Converteer veilig naar float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_weather_points(start_date: date, end_date: date) -> list[WeatherPoint]:
    """Lees uurlijkse weerdata voor gisteren en vandaag uit Open-Meteo."""
    payload = fetch_json(
        OPEN_METEO_URL,
        {
            "latitude": REFERENCE_LOCATION["latitude"],
            "longitude": REFERENCE_LOCATION["longitude"],
            "timezone": "Europe/Amsterdam",
            "wind_speed_unit": "kmh",
            "hourly": [
                "wind_speed_10m",
                "wind_direction_10m",
                "pressure_msl",
                "temperature_2m",
                "precipitation",
                "cape",
            ],
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        },
    )

    hourly = payload.get("hourly") if isinstance(payload, dict) else {}
    times = hourly.get("time") if isinstance(hourly, dict) else []
    wind_values = hourly.get("wind_speed_10m") if isinstance(hourly, dict) else []
    direction_values = hourly.get("wind_direction_10m") if isinstance(hourly, dict) else []
    pressure_values = hourly.get("pressure_msl") if isinstance(hourly, dict) else []
    temperature_values = hourly.get("temperature_2m") if isinstance(hourly, dict) else []
    precipitation_values = hourly.get("precipitation") if isinstance(hourly, dict) else []
    cape_values = hourly.get("cape") if isinstance(hourly, dict) else []

    points: list[WeatherPoint] = []
    for raw_time, raw_wind, raw_direction, raw_pressure, raw_temp, raw_precip, raw_cape in zip(
        times or [],
        wind_values or [],
        direction_values or [],
        pressure_values or [],
        temperature_values or [],
        precipitation_values or [],
        cape_values or [],
    ):
        wind_speed_kmh = to_float(raw_wind)
        wind_direction_deg = to_float(raw_direction)
        pressure_hpa = to_float(raw_pressure)
        temperature_c = to_float(raw_temp)
        precipitation_mm = to_float(raw_precip)
        cape_j_kg = to_float(raw_cape)

        if None in (wind_speed_kmh, wind_direction_deg, pressure_hpa, temperature_c, precipitation_mm, cape_j_kg):
            continue

        try:
            timestamp = datetime.fromisoformat(str(raw_time))
        except ValueError:
            continue

        points.append(
            WeatherPoint(
                timestamp=timestamp.replace(tzinfo=TIMEZONE),
                wind_speed_kmh=float(wind_speed_kmh),
                wind_direction_deg=float(wind_direction_deg),
                pressure_hpa=float(pressure_hpa),
                temperature_c=float(temperature_c),
                precipitation_mm=float(precipitation_mm),
                cape_j_kg=float(cape_j_kg),
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


def average_wind_direction(points: list[WeatherPoint]) -> float | None:
    """Bepaal gemiddelde windrichting met vectoren."""
    directions = [math.radians(point.wind_direction_deg) for point in points]
    if not directions:
        return None

    x_component = mean(math.cos(value) for value in directions)
    y_component = mean(math.sin(value) for value in directions)

    if x_component == 0 and y_component == 0:
        return None

    angle = math.degrees(math.atan2(y_component, x_component))
    return round((angle + 360) % 360, 1)


def total_precipitation(points: list[WeatherPoint]) -> float:
    """Tel neerslag in een puntreeks op."""
    return round(sum(point.precipitation_mm for point in points), 1)


def maximum_value(points: list[WeatherPoint], field_name: str) -> float | None:
    """Pak de hoogste waarde van een reeks."""
    values = [getattr(point, field_name) for point in points]
    if not values:
        return None
    return float(max(values))


def bft_from_kmh(wind_speed_kmh: float) -> int:
    """Zet km/u grof om naar Beaufort."""
    thresholds = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
    for index, threshold in enumerate(thresholds):
        if wind_speed_kmh <= threshold:
            return index
    return 12


def wind_label_from_degrees(wind_direction_deg: float | None) -> str:
    """Zet graden om naar korte windstreek."""
    if wind_direction_deg is None:
        return "Onbekend"

    labels = [
        "N", "NNO", "NO", "ONO",
        "O", "OZO", "ZO", "ZZO",
        "Z", "ZZW", "ZW", "WZW",
        "W", "WNW", "NW", "NNW",
    ]
    index = int(((wind_direction_deg % 360) + 11.25) // 22.5) % len(labels)
    return labels[index]


def wind_condition(wind_speed_kmh: float) -> str:
    """Vertaal windsnelheid naar een eenvoudige conditie."""
    if wind_speed_kmh < 10:
        return "lage_wind"
    if wind_speed_kmh <= 25:
        return "matige_wind"
    return "harde_wind"


def pressure_condition(first_pressure: float, last_pressure: float, pressure_range: float) -> str:
    """Vertaal drukverandering en schommeling naar een conditie."""
    delta_hpa = round(last_pressure - first_pressure, 1)
    if pressure_range > 6:
        return "instabiele_druk"
    if delta_hpa <= -2:
        return "dalende_druk"
    if delta_hpa >= 2:
        return "stijgende_druk"
    return "stabiele_druk"


def temperature_condition(temp_delta_c: float) -> str:
    """Vertaal temperatuurverandering naar een conditie."""
    if temp_delta_c <= -2.5:
        return "temperatuurdaling"
    if abs(temp_delta_c) <= 1.5:
        return "stabiele_temperatuur"
    return "temperatuurstijging"


def rain_condition(total_precip_mm: float) -> str:
    """Vertaal avondneerslag naar een conditie."""
    if total_precip_mm >= 6:
        return "zware_regen"
    if total_precip_mm >= 0.5:
        return "lichte_regen"
    return "droge_avond"


def thunder_condition(max_cape_j_kg: float) -> str | None:
    """Gebruik CAPE als eenvoudige onweersignalering."""
    if max_cape_j_kg >= 800:
        return "onweer_risico"
    return None


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


def clamp_score(value: int) -> int:
    """Houd scores tussen 1 en 5."""
    return max(1, min(5, int(value)))


def build_score(
    *,
    pressure_state: str,
    temp_state: str,
    wind_state: str,
    rain_state: str,
    thunder_state: str | None,
    season_key: str,
) -> int:
    """Bepaal een eenvoudige visscore van 1 tot 5."""
    score = 3

    if pressure_state == "stabiele_druk":
        score += 1
    elif pressure_state == "dalende_druk":
        score += 0
    elif pressure_state in {"stijgende_druk", "instabiele_druk"}:
        score -= 1

    if temp_state == "stabiele_temperatuur":
        score += 1
    elif temp_state == "temperatuurdaling":
        score -= 1

    if wind_state == "matige_wind":
        score += 1
    elif wind_state == "harde_wind":
        score -= 1

    if rain_state == "zware_regen":
        score -= 1

    if thunder_state == "onweer_risico":
        score -= 2

    if season_key == "herfst":
        score += 1
    elif season_key == "winter":
        score -= 1

    return clamp_score(score)


def season_best_time(season_key: str, rain_state: str, thunder_state: str | None) -> str:
    """Kies een passend vismoment per seizoen en weerbeeld."""
    if thunder_state == "onweer_risico" or rain_state == "zware_regen":
        return "Kort droog venster"
    if season_key == "zomer":
        return "Avond / nacht"
    if season_key == "herfst":
        return "Late middag / avond"
    if season_key == "winter":
        return "Middag"
    return "Avond"


def build_tip(
    rules: list[dict[str, Any]],
    ordered_conditions: list[str],
    season_key: str,
    score: int,
) -> str:
    """Bepaal de hoofdtip voor de visdag."""
    for condition in ordered_conditions:
        advice = find_rule(rules, condition, "tip")
        if advice:
            return advice

    season_tip = find_rule(rules, season_key, "tip")
    if season_tip:
        return season_tip

    if score >= 4:
        return "Richt je op schemer, actief water en voorspelbare stekken."

    return "Vis compacter en kies beschutte stekken."


def build_sea_score(
    *,
    tide_summary: TideSummary | None,
    pressure_state: str,
    wind_state: str,
    thunder_state: str | None,
) -> int:
    """Schat een compacte score voor zee op basis van getij en weer."""
    score = 2

    if pressure_state in {"stabiele_druk", "dalende_druk"}:
        score += 1
    if wind_state == "harde_wind":
        score -= 1
    if thunder_state == "onweer_risico":
        score -= 1

    if tide_summary is None:
        return clamp_score(score)

    if tide_summary.amplitude_cm >= 140:
        score += 1
    elif tide_summary.amplitude_cm < 80:
        score -= 1

    if tide_summary.next_extreme is not None:
        hours_until = (tide_summary.next_extreme.timestamp - local_now()).total_seconds() / 3600
        if 0 <= hours_until <= 3:
            score += 1

    return clamp_score(score)


def build_sea_profile_advice(
    tide_summary: TideSummary | None,
    wind_state: str,
    thunder_state: str | None,
) -> str:
    """Maak een korte zee-adviesregel met getijverwijzing."""
    if tide_summary is None or tide_summary.next_extreme is None:
        return "Getijbron tijdelijk niet bereikbaar; beoordeel zee later opnieuw rond kentering."

    next_extreme = tide_summary.next_extreme
    window_label = tide_summary.active_window_label or f"rond {format_local_timestamp(next_extreme.timestamp)}"
    advice = (
        f"{tide_summary.location_label} geeft {next_extreme.kind} {format_local_timestamp(next_extreme.timestamp)} "
        f"({next_extreme.level_cm:+.0f} cm {tide_summary.reference_plane}); vis vooral {window_label}."
    )

    if thunder_state == "onweer_risico":
        return f"{advice} Houd wel rekening met onweerskans op open water."
    if wind_state == "harde_wind":
        return f"{advice} Kies bij stevige wind een beschutte pier of havenmond."
    return advice


def build_profile_advice(
    profile_name: str,
    season_key: str,
    pressure_state: str,
    *,
    tide_summary: TideSummary | None = None,
    wind_state: str = "matige_wind",
    thunder_state: str | None = None,
) -> str:
    """Maak een korte adviesregel per visprofiel."""
    if profile_name == "Roofvis":
        if pressure_state == "stabiele_druk":
            return "Stabiele druk en structuurwater maken roofvis interessanter."
        if pressure_state == "dalende_druk":
            return "Licht dalende druk kan roofvis activeren, maar blijf mobiel."
        return "Roofvis vraagt nu om strakker kiezen van tijd en beschutting."

    if profile_name == "Meerval":
        if season_key == "zomer":
            return "Warme zomeravond en nacht blijven de beste kans voor meerval."
        return "Meerval wordt interessanter zodra temperatuur en nachtactiviteit oplopen."

    return build_sea_profile_advice(tide_summary, wind_state, thunder_state)


def build_profiles(
    *,
    overall_score: int,
    season_key: str,
    pressure_state: str,
    wind_state: str,
    thunder_state: str | None,
    warm_evening: bool,
    tide_summary: TideSummary | None = None,
) -> list[VisProfile]:
    """Bouw compacte profielscores op voor drie visrichtingen."""
    roofvis_score = overall_score
    if season_key == "herfst":
        roofvis_score += 1
    if pressure_state in {"stabiele_druk", "dalende_druk"}:
        roofvis_score += 1
    if wind_state == "harde_wind":
        roofvis_score -= 1
    if thunder_state == "onweer_risico":
        roofvis_score -= 1

    meerval_score = 2
    if warm_evening:
        meerval_score += 1
    if season_key == "zomer":
        meerval_score += 1
    if pressure_state in {"stabiele_druk", "dalende_druk"}:
        meerval_score += 1
    if thunder_state == "onweer_risico":
        meerval_score -= 1

    sea_score = build_sea_score(
        tide_summary=tide_summary,
        pressure_state=pressure_state,
        wind_state=wind_state,
        thunder_state=thunder_state,
    )

    return [
        VisProfile(
            name="Roofvis",
            score=clamp_score(roofvis_score),
            advice=build_profile_advice(
                "Roofvis",
                season_key,
                pressure_state,
                tide_summary=tide_summary,
                wind_state=wind_state,
                thunder_state=thunder_state,
            ),
        ),
        VisProfile(
            name="Meerval",
            score=clamp_score(meerval_score),
            advice=build_profile_advice(
                "Meerval",
                season_key,
                pressure_state,
                tide_summary=tide_summary,
                wind_state=wind_state,
                thunder_state=thunder_state,
            ),
        ),
        VisProfile(
            name="Zee",
            score=sea_score,
            advice=build_profile_advice(
                "Zee",
                season_key,
                pressure_state,
                tide_summary=tide_summary,
                wind_state=wind_state,
                thunder_state=thunder_state,
            ),
        ),
    ]


def build_details(
    rules: list[dict[str, Any]],
    ordered_conditions: list[str],
    *,
    pressure_delta_48h: float,
    pressure_range_48h: float,
    temp_delta_c: float,
    wind_avg_kmh: float,
    evening_precip_mm: float,
    max_cape_j_kg: float,
    season_label: str,
    tide_summary: TideSummary | None = None,
    tide_error: str | None = None,
) -> list[str]:
    """Maak compacte analyse-regels voor de agentpagina."""
    details: list[str] = []

    season_detail = find_rule(rules, season_label.lower(), "detail")
    if season_detail:
        details.append(season_detail)

    for condition in ordered_conditions:
        advice = find_rule(rules, condition, "detail")
        if advice and advice not in details:
            details.append(advice)

    details.append(
        f"Luchtdruktrend over 48 uur: {pressure_delta_48h:+.1f} hPa, "
        f"schommeling circa {pressure_range_48h:.1f} hPa."
    )
    details.append(
        f"Temperatuurtrend: {temp_delta_c:+.1f} C; wind gemiddeld {wind_avg_kmh:.0f} km/u."
    )
    details.append(
        f"Vanmiddag naar vanavond wordt circa {evening_precip_mm:.1f} mm neerslag verwacht; "
        f"CAPE-piek rond {max_cape_j_kg:.0f} J/kg."
    )

    if tide_summary is not None and tide_summary.next_extreme is not None:
        next_extreme = tide_summary.next_extreme
        next_label = (
            f"RWS getij ({tide_summary.location_label}): {next_extreme.kind} "
            f"{format_local_timestamp(next_extreme.timestamp)} op {next_extreme.level_cm:+.0f} cm "
            f"{tide_summary.reference_plane}."
        )
        details.append(next_label)
        if tide_summary.following_extreme is not None:
            following = tide_summary.following_extreme
            details.append(
                f"Daarna volgt {following.kind} {format_local_timestamp(following.timestamp)}; "
                f"tijslag komende 24 uur circa {tide_summary.amplitude_cm:.0f} cm."
            )
        elif tide_summary.active_window_label:
            details.append(
                f"Actief zeevenster vooral {tide_summary.active_window_label}; "
                f"tijslag circa {tide_summary.amplitude_cm:.0f} cm."
            )
    elif tide_error:
        details.append("Getijdata van Rijkswaterstaat was tijdelijk niet bereikbaar; zeeadvies draait nu alleen op weercondities.")

    return details


def tide_best_time(tide_summary: TideSummary | None) -> str | None:
    """Vertaal een tijvenster naar een compacte Beste tijd-tekst."""
    if tide_summary is None or tide_summary.next_extreme is None:
        return None
    if tide_summary.active_window_label:
        return f"{tide_summary.active_window_label} (zee)"
    return f"Rond {tide_summary.next_extreme.kind} {format_local_timestamp(tide_summary.next_extreme.timestamp)}"


def blend_tip_with_tide_tip(base_tip: str, tide_summary: TideSummary | None) -> str:
    """Voeg een korte getijhaak toe als die echt helpt."""
    if tide_summary is None or tide_summary.next_extreme is None:
        return base_tip

    hours_until = (tide_summary.next_extreme.timestamp - local_now()).total_seconds() / 3600
    if 0 <= hours_until <= 4:
        return (
            f"{base_tip} Voor zout is {tide_summary.active_window_label or 'de kentering'} "
            f"bij {tide_summary.location_label} extra interessant."
        )
    return base_tip


def extract_bft(value: str) -> int | None:
    """Lees een Beaufort-getal uit bestaande tekst."""
    match = re.search(r"(\d+)\s*Bft", value, flags=re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def is_generic_tip(value: str) -> bool:
    """Herken oude, niet-actionable samenvattingen die geen echte vistip zijn."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True

    generic_values = {
        "prima ochtend",
        "prima middag",
        "prima avond",
        "redelijke ochtend",
        "redelijke middag",
        "redelijke avond",
        "goede ochtend",
        "goede middag",
        "goede avond",
        "matige ochtend",
        "matige middag",
        "matige avond",
    }
    actionable_markers = (
        "schemer",
        "nacht",
        "luwte",
        "brug",
        "haven",
        "diep",
        "beschut",
        "druk",
        "wind",
        "regen",
        "onweer",
        "paai",
        "structuur",
        "sessie",
    )

    if normalized in generic_values:
        return True

    if any(marker in normalized for marker in actionable_markers):
        return False

    return normalized.startswith(("prima ", "redelijke ", "goede ", "matige "))


def payload_has_profiles(payload: Any) -> bool:
    """Controleer of visdata al profieladvies bevat."""
    if not isinstance(payload, dict):
        return False

    profiles = payload.get("profiles")
    return isinstance(profiles, list) and len(profiles) >= 3


def migrate_existing_payload(payload: Any) -> dict[str, Any] | None:
    """Verrijk oudere visdata als live weerdata tijdelijk ontbreekt."""
    if not isinstance(payload, dict):
        return None

    rules = load_rules()
    now = local_now()
    season_key, season_label = detect_season(now.date())
    items = payload.get("items")
    if not isinstance(items, list):
        return None

    item_map = {
        str(item.get("label", "")).strip(): str(item.get("value", "")).strip()
        for item in items
        if isinstance(item, dict)
    }

    wind_text = item_map.get("Wind", "ZW 3 Bft")
    pressure_text = item_map.get("Luchtdruk", "Stabiel")
    best_time = item_map.get("Beste tijd", season_best_time(season_key, "droge_avond", None))
    pressure_match = re.search(r"(\d+(?:[.,]\d+)?)\s*hPa", pressure_text, flags=re.IGNORECASE)
    pressure_avg_hpa = float(pressure_match.group(1).replace(",", ".")) if pressure_match else None

    bft = extract_bft(wind_text) or 3
    wind_state = "harde_wind" if bft >= 6 else "matige_wind"
    wind_direction_label = re.search(r"\b(NNO|ONO|ZZO|WZW|WNW|NNW|OZO|ZZW|NO|ZO|ZW|NW|N|O|Z|W)\b", wind_text, flags=re.IGNORECASE)
    normalized_direction = wind_direction_label.group(1).upper() if wind_direction_label else "ZW"
    direction_map = {
        "N": 0.0, "NNO": 22.5, "NO": 45.0, "ONO": 67.5,
        "O": 90.0, "OZO": 112.5, "ZO": 135.0, "ZZO": 157.5,
        "Z": 180.0, "ZZW": 202.5, "ZW": 225.0, "WZW": 247.5,
        "W": 270.0, "WNW": 292.5, "NW": 315.0, "NNW": 337.5,
    }
    normalized_pressure = pressure_text.lower()
    if "dalend" in normalized_pressure:
        pressure_state = "dalende_druk"
    elif "stijgend" in normalized_pressure:
        pressure_state = "stijgende_druk"
    elif "instabiel" in normalized_pressure:
        pressure_state = "instabiele_druk"
    else:
        pressure_state = "stabiele_druk"

    temp_state = "stabiele_temperatuur"
    rain_state = "droge_avond"
    thunder_state = None
    score = clamp_score(int(payload.get("score", build_score(
        pressure_state=pressure_state,
        temp_state=temp_state,
        wind_state=wind_state,
        rain_state=rain_state,
        thunder_state=thunder_state,
        season_key=season_key,
    ))))
    profiles = build_profiles(
        overall_score=score,
        season_key=season_key,
        pressure_state=pressure_state,
        wind_state=wind_state,
        thunder_state=thunder_state,
        warm_evening=season_key == "zomer",
    )
    existing_tip = item_map.get("Tip", "").strip()
    tip = existing_tip if not is_generic_tip(existing_tip) else build_tip(
        rules,
        [pressure_state, wind_state, rain_state, season_key],
        season_key,
        score,
    )
    details = build_details(
        rules,
        [pressure_state, wind_state, rain_state, season_key],
        pressure_delta_48h=0.0,
        pressure_range_48h=0.0,
        temp_delta_c=0.0,
        wind_avg_kmh=18.0,
        evening_precip_mm=0.0,
        max_cape_j_kg=0.0,
        season_label=season_label,
    )
    if item_map.get("Conclusie"):
        details.insert(0, f"Bestaande conclusie: {item_map['Conclusie']}.")

    return {
        "updated_at": utc_now_iso(),
        "status": "Visadvies vandaag",
        "score": score,
        "items": [
            {"label": "Wind", "value": wind_text},
            {"label": "Luchtdruk", "value": pressure_text},
            {"label": "Beste tijd", "value": best_time},
            {"label": "Tip", "value": tip},
        ],
        "details": details,
        "profiles": [
            {"name": profile.name, "score": profile.score, "advice": profile.advice}
            for profile in profiles
        ],
        "context": {
            "reference_location": REFERENCE_LOCATION["label"],
            "season": season_key,
            "season_label": season_label,
            "pressure_state": pressure_state,
            "temperature_state": temp_state,
            "wind_state": wind_state,
            "rain_state": rain_state,
            "thunder_state": thunder_state,
            "pressure_delta_48h_hpa": None,
            "pressure_range_48h_hpa": None,
            "temperature_delta_c": None,
            "wind_avg_kmh": 18.0,
            "wind_direction_deg": direction_map.get(normalized_direction, 225.0),
            "wind_direction_label": normalized_direction,
            "pressure_avg_hpa": pressure_avg_hpa,
            "evening_precipitation_mm": 0.0,
            "evening_temperature_c": None,
            "max_cape_j_kg": 0.0,
        },
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Rijkswaterstaat Waterinfo", "url": WATERINFO_TIDE_VIEW_URL},
            {"name": "Visregels", "note": "agents/vissen_rules.json"},
        ],
        "url": VISSEN_URL,
    }


def build_advice() -> VisAdvice:
    """Maak visadvies op basis van Open-Meteo, druktrend en vaste regels."""
    rules = load_rules()
    now = local_now()
    season_key, season_label = detect_season(now.date())
    start_date = now.date() - timedelta(days=1)
    end_date = now.date()
    points = fetch_weather_points(start_date, end_date)

    if not points:
        raise RuntimeError("Geen uurlijkse weerdata ontvangen van Open-Meteo.")

    tide_summary: TideSummary | None = None
    tide_error: str | None = None
    try:
        tide_summary = build_tide_summary(now)
    except Exception as error:
        tide_error = str(error)

    future_points = [point for point in points if point.timestamp.astimezone(TIMEZONE) >= now]
    evening_points = points_between(points, 17, 23, after=now)
    active_window = evening_points or future_points or points_between(points, 12, 23) or points

    pressure_points = points[-48:] if len(points) >= 48 else points
    first_pressure = pressure_points[0].pressure_hpa
    last_pressure = pressure_points[-1].pressure_hpa
    pressure_range = max(point.pressure_hpa for point in pressure_points) - min(point.pressure_hpa for point in pressure_points)
    pressure_delta_48h = round(last_pressure - first_pressure, 1)

    recent_points = points[-12:] if len(points) >= 12 else points
    previous_points = points[-24:-12] if len(points) >= 24 else points[: max(1, len(points) // 2)]
    recent_temp = average_value(recent_points, "temperature_c") or 0.0
    previous_temp = average_value(previous_points, "temperature_c") or recent_temp
    temperature_delta_c = round(recent_temp - previous_temp, 1)

    wind_avg_kmh = average_value(active_window, "wind_speed_kmh") or 0.0
    wind_direction_deg = average_wind_direction(active_window)
    pressure_avg_hpa = average_value(active_window, "pressure_hpa") or 0.0
    evening_precip_mm = total_precipitation(evening_points or active_window)
    max_cape_j_kg = maximum_value(active_window, "cape_j_kg") or 0.0
    evening_temperature_c = average_value(evening_points or active_window, "temperature_c") or 0.0

    pressure_state = pressure_condition(first_pressure, last_pressure, pressure_range)
    temp_state = temperature_condition(temperature_delta_c)
    wind_state = wind_condition(wind_avg_kmh)
    rain_state = rain_condition(evening_precip_mm)
    thunder_state = thunder_condition(max_cape_j_kg)

    ordered_conditions = [pressure_state, temp_state, wind_state, rain_state, season_key]
    if thunder_state:
        ordered_conditions.insert(0, thunder_state)

    score = build_score(
        pressure_state=pressure_state,
        temp_state=temp_state,
        wind_state=wind_state,
        rain_state=rain_state,
        thunder_state=thunder_state,
        season_key=season_key,
    )
    best_time = season_best_time(season_key, rain_state, thunder_state)
    if tide_summary is not None and tide_summary.next_extreme is not None:
        hours_until_tide = (tide_summary.next_extreme.timestamp - now).total_seconds() / 3600
        tide_window = tide_best_time(tide_summary)
        if tide_window and 0 <= hours_until_tide <= 5:
            best_time = tide_window

    tip = blend_tip_with_tide_tip(build_tip(rules, ordered_conditions, season_key, score), tide_summary)
    profiles = build_profiles(
        overall_score=score,
        season_key=season_key,
        pressure_state=pressure_state,
        wind_state=wind_state,
        thunder_state=thunder_state,
        warm_evening=evening_temperature_c >= 18,
        tide_summary=tide_summary,
    )
    details = build_details(
        rules,
        ordered_conditions,
        pressure_delta_48h=pressure_delta_48h,
        pressure_range_48h=round(pressure_range, 1),
        temp_delta_c=temperature_delta_c,
        wind_avg_kmh=wind_avg_kmh,
        evening_precip_mm=evening_precip_mm,
        max_cape_j_kg=max_cape_j_kg,
        season_label=season_label,
        tide_summary=tide_summary,
        tide_error=tide_error,
    )

    return VisAdvice(
        status="Visadvies vandaag",
        score=score,
        wind_value=f"{wind_avg_kmh:.0f} km/u ({bft_from_kmh(wind_avg_kmh)} Bft)",
        pressure_value=f"{pressure_avg_hpa:.0f} hPa ({pressure_state.replace('_', ' ')})",
        best_time=best_time,
        tip=tip,
        details=details,
        profiles=profiles,
        context={
            "reference_location": REFERENCE_LOCATION["label"],
            "season": season_key,
            "season_label": season_label,
            "pressure_state": pressure_state,
            "temperature_state": temp_state,
            "wind_state": wind_state,
            "rain_state": rain_state,
            "thunder_state": thunder_state,
            "pressure_delta_48h_hpa": pressure_delta_48h,
            "pressure_range_48h_hpa": round(pressure_range, 1),
            "temperature_delta_c": temperature_delta_c,
            "wind_avg_kmh": round(wind_avg_kmh, 1),
            "wind_direction_deg": wind_direction_deg,
            "wind_direction_label": wind_label_from_degrees(wind_direction_deg),
            "pressure_avg_hpa": round(pressure_avg_hpa, 1),
            "evening_precipitation_mm": evening_precip_mm,
            "evening_temperature_c": round(evening_temperature_c, 1),
            "max_cape_j_kg": round(max_cape_j_kg, 1),
            "tide_available": tide_summary is not None,
            "tide_error": tide_error,
            "tide_location": tide_summary.location_label if tide_summary else TIDE_REFERENCE_STATION["label"],
            "tide_location_code": tide_summary.location_code if tide_summary else TIDE_REFERENCE_STATION["location_code"],
            "tide_reference_plane": tide_summary.reference_plane if tide_summary else "NAP",
            "tide_timezone": tide_summary.timezone_identifier if tide_summary else None,
            "tide_range_value": tide_summary.range_value if tide_summary else None,
            "tide_amplitude_cm": tide_summary.amplitude_cm if tide_summary else None,
            "tide_active_window": tide_summary.active_window_label if tide_summary else None,
            "tide_current_level_cm": tide_summary.current_level_cm if tide_summary else None,
            "tide_next_extreme": (
                {
                    "kind": tide_summary.next_extreme.kind,
                    "time": tide_summary.next_extreme.timestamp.isoformat(),
                    "level_cm": tide_summary.next_extreme.level_cm,
                }
                if tide_summary and tide_summary.next_extreme
                else None
            ),
            "tide_following_extreme": (
                {
                    "kind": tide_summary.following_extreme.kind,
                    "time": tide_summary.following_extreme.timestamp.isoformat(),
                    "level_cm": tide_summary.following_extreme.level_cm,
                }
                if tide_summary and tide_summary.following_extreme
                else None
            ),
        },
    )


def build_fallback_payload(error: Exception) -> dict[str, Any]:
    """Maak een geldige fallback als er nog geen visdata bestaat."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Visadvies vandaag - bronfout",
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
        "profiles": [
            {"name": "Roofvis", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
            {"name": "Meerval", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
            {"name": "Zee", "score": 1, "advice": "Nog geen actuele analyse beschikbaar."},
        ],
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Rijkswaterstaat Waterinfo", "url": WATERINFO_TIDE_VIEW_URL},
            {"name": "Visregels", "note": "Lokaal kennisbestand"},
        ],
        "context": {
            "reference_location": REFERENCE_LOCATION["label"],
            "wind_direction_label": "Onbekend",
        },
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
        "profiles": [
            {
                "name": profile.name,
                "score": profile.score,
                "advice": profile.advice,
            }
            for profile in advice.profiles
        ],
        "context": advice.context,
        "sources": [
            {"name": "Open-Meteo Forecast API", "url": OPEN_METEO_DOCS_URL},
            {"name": "Rijkswaterstaat Waterinfo", "url": WATERINFO_TIDE_VIEW_URL},
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
        if current_payload is not None:
            migrated_payload = migrate_existing_payload(current_payload)
            if migrated_payload is not None:
                changed = save_payload(migrated_payload)
                print(
                    f"[DONE] Bestaande visdata bijgewerkt in {OUTPUT_PATH} "
                    f"({'gewijzigd' if changed else 'ongewijzigd'})."
                )
                return

            if payload_has_profiles(current_payload):
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
