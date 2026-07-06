"""Haal echte sportitems op voor voetbal, darts en Formule 1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from json_store import load_json, save_json_if_changed


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT_DIR / "agents" / "sport_sources.json"
OUTPUT_PATH = ROOT_DIR / "data" / "sport.json"
DEFAULT_DASHBOARD_URL = "https://mailbvandongen-eng.github.io/sport-op-tv/"
USER_AGENT = "BobOS SportAgent/0.3"
MAX_ITEMS = 12

try:
    TIMEZONE = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:
    TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


@dataclass(frozen=True)
class SportItem:
    """Compact sportitem voor BobOS."""

    start_at: datetime
    title: str
    category: str
    source: str

    @property
    def time(self) -> str:
        return self.start_at.astimezone(TIMEZONE).strftime("%H:%M")


def load_sources() -> dict[str, Any]:
    """Lees alle sportbronnen uit een enkel configuratiebestand."""
    with SOURCES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("sport_sources.json heeft geen geldig object als basis.")

    return payload


def utc_now_iso() -> str:
    """Geef een UTC-tijd terug zonder fracties."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def fetch_text(url: str) -> str:
    """Laad tekst van een externe bron."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        },
    )

    with urlopen(request, timeout=20) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_json(url: str) -> Any:
    """Laad JSON van een externe bron."""
    return json.loads(fetch_text(url))


def today_local() -> date:
    """Geef de lokale datum terug voor filtering van vandaag."""
    return datetime.now(TIMEZONE).date()


def parse_utc_datetime(value: str) -> datetime | None:
    """Maak een timezone-aware datetime van een ISO UTC-waarde."""
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_local_datetime(day_value: str, time_value: str) -> datetime | None:
    """Maak een lokale datetime zoals de browser-app die ook gebruikt."""
    try:
        parsed = datetime.strptime(f"{day_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None

    return parsed.replace(tzinfo=TIMEZONE)


def same_local_day(moment: datetime) -> bool:
    """Controleer of een datetime in de lokale BobOS-dag valt."""
    return moment.astimezone(TIMEZONE).date() == today_local()


def clean_team_name(name: str) -> str:
    """Maak teamnamen iets compacter."""
    cleaned = str(name).replace(" FC", "").replace(" AFC", "").strip()
    return cleaned or str(name).strip()


def clean_darts_name(name: str) -> str:
    """Maak toernooititels wat korter."""
    cleaned = re.sub(r"\s+\d{4}$", "", name.strip())
    return cleaned or "Darts"


def get_pdc_participant_name(value: object) -> str:
    """Lees een spelernaam uit verschillende PDC-velden."""
    if isinstance(value, dict):
        for key in ("name", "displayName", "shortName"):
            candidate = str(value.get(key, "")).strip()
            if candidate:
                return candidate

    return str(value or "").strip()


def normalize_title(home: str, away: str, fallback: str) -> str:
    """Maak een nette titel voor het sportitem."""
    if home and away:
        return f"{home} - {away}"

    if home:
        return home

    return fallback or "Sportitem"


def fetch_openfootball_items(sources: dict[str, Any]) -> list[SportItem]:
    """Lees voetbalwedstrijden uit OpenFootball."""
    items: list[SportItem] = []
    reachable = False
    openfootball = sources.get("openfootball") or {}
    base_url = str(openfootball.get("base_url", "")).rstrip("/")
    leagues = openfootball.get("leagues") or []

    if not base_url or not isinstance(leagues, list):
        print("[WARN] OpenFootball-config ontbreekt of is ongeldig.")
        return items

    for league in leagues:
        if not isinstance(league, dict):
            continue

        filename = str(league.get("file", "")).strip()
        competition = str(league.get("name", "")).strip() or "Voetbal"
        if not filename:
            continue

        url = f"{base_url}/{filename}"

        try:
            payload = fetch_json(url)
            reachable = True
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"[WARN] OpenFootball mislukt voor {competition}: {error}")
            continue

        for match in (payload.get("matches") if isinstance(payload, dict) else []) or []:
            if not isinstance(match, dict):
                continue

            start_at = parse_local_datetime(
                str(match.get("date", "")).strip(),
                str(match.get("time") or "15:00").strip(),
            )
            if not start_at or not same_local_day(start_at):
                continue

            home = clean_team_name(str(match.get("team1", "")).strip())
            away = clean_team_name(str(match.get("team2", "")).strip())
            title = normalize_title(home, away, competition)

            items.append(
                SportItem(
                    start_at=start_at,
                    title=title,
                    category=competition,
                    source=f"OpenFootball ({competition})",
                )
            )

    fetch_openfootball_items.reachable = reachable
    return items


def fetch_espn_items(sources: dict[str, Any]) -> list[SportItem]:
    """Lees voetbalwedstrijden uit ESPN."""
    items: list[SportItem] = []
    reachable = False
    espn = sources.get("espn") or {}
    base_url = str(espn.get("base_url", "")).rstrip("/")
    competitions = espn.get("competitions") or []

    if not base_url or not isinstance(competitions, list):
        print("[WARN] ESPN-config ontbreekt of is ongeldig.")
        return items

    today = today_local()
    start_key = (today - timedelta(days=1)).strftime("%Y%m%d")
    end_key = (today + timedelta(days=1)).strftime("%Y%m%d")

    for competition in competitions:
        if not isinstance(competition, dict):
            continue

        slug = str(competition.get("slug", "")).strip()
        name = str(competition.get("name", "")).strip() or "Voetbal"
        if not slug:
            continue

        url = f"{base_url}/{slug}/scoreboard?dates={start_key}-{end_key}&limit=1000"

        try:
            payload = fetch_json(url)
            reachable = True
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"[WARN] ESPN mislukt voor {name}: {error}")
            continue

        for event in (payload.get("events") if isinstance(payload, dict) else []) or []:
            if not isinstance(event, dict):
                continue

            start_at = parse_utc_datetime(str(event.get("date", "")).strip())
            if not start_at or not same_local_day(start_at):
                continue

            competition_data = (event.get("competitions") or [{}])[0]
            competitors = competition_data.get("competitors") or []
            home_team = next((row for row in competitors if row.get("homeAway") == "home"), {})
            away_team = next((row for row in competitors if row.get("homeAway") == "away"), {})

            home = str(
                ((home_team.get("team") or {}).get("shortDisplayName"))
                or ((home_team.get("team") or {}).get("displayName"))
                or ""
            ).strip()
            away = str(
                ((away_team.get("team") or {}).get("shortDisplayName"))
                or ((away_team.get("team") or {}).get("displayName"))
                or ""
            ).strip()

            title = normalize_title(home, away, str(event.get("name", "")).strip())
            items.append(
                SportItem(
                    start_at=start_at,
                    title=title,
                    category=name,
                    source=f"ESPN ({name})",
                )
            )

    fetch_espn_items.reachable = reachable
    return items


def fetch_f1_items(sources: dict[str, Any]) -> list[SportItem]:
    """Lees F1-sessies uit OpenF1."""
    openf1 = sources.get("openf1") or {}
    base_url = str(openf1.get("base_url", "")).rstrip("/")
    if not base_url:
        print("[WARN] OpenF1-config ontbreekt of is ongeldig.")
        return []

    url = f"{base_url}/sessions?year={today_local().year}"

    try:
        payload = fetch_json(url)
        fetch_f1_items.reachable = True
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"[WARN] OpenF1 mislukt: {error}")
        fetch_f1_items.reachable = False
        return []

    items: list[SportItem] = []
    for session in payload if isinstance(payload, list) else []:
        if not isinstance(session, dict):
            continue

        start_at = parse_utc_datetime(str(session.get("date_start", "")).strip())
        if not start_at or not same_local_day(start_at):
            continue

        title = str(session.get("session_name", "")).strip() or "F1-sessie"
        country = str(session.get("country_name", "")).strip()
        category = f"GP {country}" if country else "Formule 1"

        items.append(
            SportItem(
                start_at=start_at,
                title=title,
                category=category,
                source="OpenF1",
            )
        )

    return items


def fetch_pdc_items(sources: dict[str, Any]) -> list[SportItem]:
    """Lees dartswedstrijden uit de PDC-feed."""
    pdc = sources.get("pdc") or {}
    fixtures_url = str(pdc.get("fixtures_url", "")).strip()
    if not fixtures_url:
        print("[WARN] PDC-config ontbreekt of is ongeldig.")
        return []

    try:
        payload = fetch_json(fixtures_url)
        fetch_pdc_items.reachable = True
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"[WARN] PDC-feed mislukt: {error}")
        fetch_pdc_items.reachable = False
        return []

    items: list[SportItem] = []
    fixtures = (payload.get("data") if isinstance(payload, dict) else []) or []

    for fixture in fixtures:
        attributes = fixture.get("attributes") if isinstance(fixture, dict) else None
        if not isinstance(attributes, dict):
            continue

        start_date = str(attributes.get("startDate", "")).strip()
        start_time = str(attributes.get("startTime", "")).strip()

        if start_time:
            start_at = parse_utc_datetime(f"{start_date}T{start_time}Z")
        else:
            start_at = parse_local_datetime(start_date, "12:00")

        if not start_at or not same_local_day(start_at):
            continue

        title = normalize_title(
            get_pdc_participant_name(attributes.get("participant1")),
            get_pdc_participant_name(attributes.get("participant2")),
            str(attributes.get("name", "")).replace(" vs ", " - ").strip(),
        )
        tournament = attributes.get("tournament") or {}
        category = clean_darts_name(str(tournament.get("name", "")).strip()) or "Darts"

        items.append(
            SportItem(
                start_at=start_at,
                title=title,
                category=category,
                source="PDC",
            )
        )

    return items


def dedupe_and_limit(items: list[SportItem]) -> list[SportItem]:
    """Houd de lijst compact, uniek en op tijd gesorteerd."""
    unique: dict[tuple[str, str, str], SportItem] = {}

    for item in sorted(items, key=lambda row: row.start_at):
        key = (
            item.time,
            item.title.strip().lower(),
            item.category.strip().lower(),
        )
        unique.setdefault(key, item)

    return list(unique.values())[:MAX_ITEMS]


def build_source_list(sources: dict[str, Any]) -> list[dict[str, str]]:
    """Maak een compacte bronlijst voor de agentpagina."""
    openfootball = sources.get("openfootball") or {}
    espn = sources.get("espn") or {}
    openf1 = sources.get("openf1") or {}
    pdc = sources.get("pdc") or {}

    source_rows = [
        {"name": "OpenFootball", "url": str(openfootball.get("base_url", "")).strip()},
        {"name": "ESPN Scoreboard", "url": str(espn.get("base_url", "")).strip()},
        {"name": "OpenF1", "url": str(openf1.get("base_url", "")).strip()},
        {"name": "PDC Fixtures", "url": str(pdc.get("fixtures_url", "")).strip()},
    ]

    return [row for row in source_rows if row["url"]]


def build_details(items: list[SportItem], sources_reachable: bool) -> list[str]:
    """Maak enkele compacte analyse-regels voor de agentpagina."""
    if not items:
        if not sources_reachable:
            return [
                "De sportbronnen waren tijdelijk niet bereikbaar, dus BobOS kon geen live selectie opbouwen.",
                "Probeer later opnieuw; falende bronnen worden overgeslagen zodra er weer verbinding is.",
            ]

        return [
            "Er zijn vandaag geen voetbal-, darts- of F1-items gevonden in de actieve bronnen.",
            "Bronnen die tijdelijk niet reageren worden overgeslagen; later opnieuw draaien kan nieuwe items opleveren.",
        ]

    categories = sorted({item.category for item in items})
    detail_lines = [
        f"{len(items)} sportitem(s) gevonden voor vandaag.",
        f"Categorieen vandaag: {', '.join(categories)}.",
        "Alleen voetbal, darts en Formule 1 worden meegenomen in BobOS.",
    ]

    return detail_lines


def build_payload(
    items: list[SportItem],
    sources: dict[str, Any],
    *,
    sources_reachable: bool,
) -> dict[str, Any]:
    """Maak de vaste BobOS JSON-structuur voor het sportdomein."""
    dashboard_url = get_dashboard_url(sources)
    if items:
        status = "Sport op TV vandaag"
    elif sources_reachable:
        status = "Geen sport gevonden voor vandaag"
    else:
        status = "Sportbronnen tijdelijk niet beschikbaar"

    return {
        "updated_at": utc_now_iso(),
        "status": status,
        "items": [
            {
                "time": item.time,
                "title": item.title,
                "category": item.category,
                "source": item.source,
                "url": dashboard_url,
            }
            for item in items
        ],
        "details": build_details(items, sources_reachable),
        "sources": build_source_list(sources),
        "url": dashboard_url,
    }


def save_payload(payload: dict[str, Any]) -> bool:
    """Schrijf het JSON-bestand alleen weg als de inhoud echt is gewijzigd."""
    return save_json_if_changed(OUTPUT_PATH, payload, ignored_keys={"updated_at"})


def has_existing_payload() -> bool:
    """Controleer of er al bruikbare sportdata op schijf staat."""
    current_payload = load_json(OUTPUT_PATH)
    return isinstance(current_payload, dict)


def collect_items(sources: dict[str, Any]) -> tuple[list[SportItem], bool]:
    """Haal echte sportitems op via de vaste JSON/API-bronnen."""
    items: list[SportItem] = []
    sources_reachable = False

    for fetcher, label in (
        (fetch_openfootball_items, "OpenFootball"),
        (fetch_espn_items, "ESPN"),
        (fetch_f1_items, "OpenF1"),
        (fetch_pdc_items, "PDC"),
    ):
        fetched = fetcher(sources)
        sources_reachable = sources_reachable or bool(getattr(fetcher, "reachable", False))
        print(f"[INFO] {label}: {len(fetched)} item(s) voor vandaag gevonden.")
        items.extend(fetched)

    selected = dedupe_and_limit(items)
    print(f"[INFO] Geselecteerde bronitems: {len(selected)}")
    for item in selected:
        print(f"[INFO] {item.time} | {item.category} | {item.title} | bron={item.source}")

    return selected, sources_reachable


def get_dashboard_url(sources: dict[str, Any] | None = None) -> str:
    """Lees de dashboardlink uit de bronconfig met een veilige fallback."""
    source_map = sources if isinstance(sources, dict) else {}
    return str(source_map.get("dashboard_url", "")).strip() or DEFAULT_DASHBOARD_URL


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    try:
        sources = load_sources()
    except Exception as error:  # pragma: no cover
        print(f"[WARN] Bronconfig kon niet worden geladen: {error}")
        sources = {"dashboard_url": DEFAULT_DASHBOARD_URL}

    try:
        items, sources_reachable = collect_items(sources)
    except Exception as error:  # pragma: no cover
        print(f"[WARN] SportAgent viel terug naar lege output: {error}")
        items = []
        sources_reachable = False

    if not sources_reachable and has_existing_payload():
        print(
            f"[DONE] Geen sportbron bereikbaar; bestaand {OUTPUT_PATH} blijft staan "
            "(ongewijzigd)."
        )
        return

    payload = build_payload(items, sources, sources_reachable=sources_reachable)
    changed = save_payload(payload)
    print(
        f"[DONE] Sportdata gecontroleerd in {OUTPUT_PATH} "
        f"({'gewijzigd' if changed else 'ongewijzigd'})."
    )


if __name__ == "__main__":
    main()
