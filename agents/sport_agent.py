"""Haal echte sportitems op via de bevestigde bronnen van Sport op TV."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "sport.json"
SPORT_URL = "https://mailbvandongen-eng.github.io/sport-op-tv/"
USER_AGENT = "BobOS SportAgent/0.2"
MAX_ITEMS = 3
OPENFOOTBALL_BASE_URL = "https://raw.githubusercontent.com/openfootball/football.json/master/2025-26"
ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
PDC_FIXTURES_URL = "https://fixtures.darts.web.gc.pdcservices.co.uk/v2?page.size=500"
OPENF1_API_URL = "https://api.openf1.org/v1"

# Deze lijsten volgen de echte bronset van de bestaande Sport op TV-app,
# maar staan hier expliciet vast zodat de agent geen homepage-config hoeft te scrapen.
OPENFOOTBALL_LEAGUES = [
    {"file": "nl.1.json", "name": "Eredivisie"},
    {"file": "en.1.json", "name": "Premier League"},
    {"file": "de.1.json", "name": "Bundesliga"},
    {"file": "es.1.json", "name": "La Liga"},
    {"file": "it.1.json", "name": "Serie A"},
    {"file": "fr.1.json", "name": "Ligue 1"},
]

ESPN_COMPETITIONS = [
    {"slug": "uefa.champions", "name": "Champions League"},
    {"slug": "uefa.europa", "name": "Europa League"},
    {"slug": "uefa.europa.conf", "name": "Conference League"},
    {"slug": "fifa.world", "name": "WK"},
    {"slug": "uefa.euro", "name": "EK"},
    {"slug": "uefa.nations", "name": "Nations League"},
    {"slug": "fifa.worldq.uefa", "name": "WK Kwalificatie"},
    {"slug": "uefa.euroq", "name": "EK Kwalificatie"},
    {"slug": "fifa.friendly", "name": "Vriendschappelijk Internationaal"},
    {"slug": "fifa.wwc", "name": "WK Vrouwen"},
    {"slug": "uefa.weuro", "name": "EK Vrouwen"},
    {"slug": "fifa.wworldq.uefa", "name": "WK Kwalificatie Vrouwen"},
    {"slug": "uefa.w.nations", "name": "Nations League Vrouwen"},
    {"slug": "fifa.friendly.w", "name": "Vriendschappelijk Internationaal Vrouwen"},
    {"slug": "ned.cup", "name": "KNVB Beker"},
    {"slug": "eng.fa", "name": "FA Cup"},
    {"slug": "ger.dfb_pokal", "name": "DFB Pokal"},
    {"slug": "esp.copa_del_rey", "name": "Copa del Rey"},
    {"slug": "ita.coppa_italia", "name": "Coppa Italia"},
    {"slug": "fra.coupe_de_france", "name": "Coupe de France"},
    {"slug": "eng.league_cup", "name": "League Cup"},
]

try:
    TIMEZONE = ZoneInfo("Europe/Amsterdam")
except ZoneInfoNotFoundError:
    # Handig op Windows-systemen waar tzdata niet apart is geinstalleerd.
    TIMEZONE = datetime.now().astimezone().tzinfo or timezone.utc


@dataclass(frozen=True)
class SportItem:
    """Compact sportitem voor de BobOS-tegel."""

    start_at: datetime
    title: str
    category: str
    source: str

    @property
    def time(self) -> str:
        return self.start_at.astimezone(TIMEZONE).strftime("%H:%M")


def utc_now_iso() -> str:
    """Geef een UTC-tijd terug zonder fracties, passend voor JSON-opslag."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def fetch_text(url: str) -> str:
    """Laad tekst van een externe bron met een kleine, nette user agent."""
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


def fetch_json(url: str) -> object:
    """Laad JSON van een externe bron."""
    return json.loads(fetch_text(url))


def today_local() -> date:
    """Geef de lokale datum terug voor filtering van 'vandaag'."""
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
    """Maak een lokale datetime die hetzelfde werkt als in de browser-app."""
    try:
        return datetime.strptime(f"{day_value} {time_value}", "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE)
    except ValueError:
        return None


def same_local_day(moment: datetime) -> bool:
    """Controleer of een datetime in de lokale BobOS-dag valt."""
    return moment.astimezone(TIMEZONE).date() == today_local()


def clean_team_name(name: str) -> str:
    """Maak teamnamen iets compacter, net als in de bestaande app."""
    cleaned = str(name).replace(" FC", "").replace(" AFC", "").strip()
    return cleaned or name.strip()


def clean_darts_name(name: str) -> str:
    """Maak toernooititels wat korter voor de dashboardtegel."""
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
    """Maak een nette titel voor de sporttegel."""
    if home and away:
        return f"{home} - {away}"

    if home:
        return home

    return fallback or "Sportitem"


def fetch_openfootball_items() -> list[SportItem]:
    """Lees voetbalwedstrijden uit OpenFootball, zoals de app dat ook doet."""
    items: list[SportItem] = []

    for league in OPENFOOTBALL_LEAGUES:
        filename = league["file"]
        competition = league["name"]
        if not filename:
            continue

        url = f"{OPENFOOTBALL_BASE_URL}/{filename}"

        try:
            payload = fetch_json(url)
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

    return items


def fetch_espn_items() -> list[SportItem]:
    """Lees voetbalwedstrijden uit ESPN, zoals de app dat ook doet."""
    items: list[SportItem] = []

    today = today_local()
    start_key = (today - timedelta(days=1)).strftime("%Y%m%d")
    end_key = (today + timedelta(days=1)).strftime("%Y%m%d")

    for competition in ESPN_COMPETITIONS:
        slug = competition["slug"]
        name = competition["name"]
        url = f"{ESPN_API_URL}/{slug}/scoreboard?dates={start_key}-{end_key}&limit=1000"

        try:
            payload = fetch_json(url)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"[WARN] ESPN mislukt voor {name}: {error}")
            continue

        events = payload.get("events") if isinstance(payload, dict) else []
        for event in events or []:
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

    return items


def fetch_f1_items() -> list[SportItem]:
    """Lees F1-sessies uit OpenF1, zoals de app dat ook doet."""
    year = today_local().year
    url = f"{OPENF1_API_URL}/sessions?year={year}"

    try:
        payload = fetch_json(url)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"[WARN] OpenF1 mislukt: {error}")
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


def fetch_pdc_items() -> list[SportItem]:
    """Lees dartswedstrijden uit de PDC-feed die de app gebruikt."""
    try:
        payload = fetch_json(PDC_FIXTURES_URL)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"[WARN] PDC-feed mislukt: {error}")
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
        category = clean_darts_name(str(tournament.get("name", "")).strip())

        items.append(
            SportItem(
                start_at=start_at,
                title=title,
                category=category or "Darts",
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


def build_payload(items: list[SportItem]) -> dict[str, object]:
    """Maak de vaste BobOS JSON-structuur voor het sportdomein."""
    status = "Sport op TV vandaag" if items else "Geen sport gevonden voor vandaag"

    return {
        "updated_at": utc_now_iso(),
        "status": status,
        "items": [
            {
                "time": item.time,
                "title": item.title,
                "category": item.category,
                "url": SPORT_URL,
            }
            for item in items
        ],
        "url": SPORT_URL,
    }


def save_payload(payload: dict[str, object]) -> None:
    """Schrijf het JSON-bestand altijd netjes weg."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def build_items() -> list[SportItem]:
    """Haal echte sportitems op via de vaste JSON/API-bronnen van Sport op TV."""
    print("[INFO] Bronnen gebruiken uit de vaste SportAgent-config.")
    print(f"[INFO] OpenFootball bron: {OPENFOOTBALL_BASE_URL}")
    print(f"[INFO] ESPN bron: {ESPN_API_URL}")
    print(f"[INFO] OpenF1 bron: {OPENF1_API_URL}")
    print(f"[INFO] PDC bron: {PDC_FIXTURES_URL}")
    items: list[SportItem] = []

    for fetcher, label in (
        (fetch_openfootball_items, "OpenFootball"),
        (fetch_espn_items, "ESPN"),
        (fetch_f1_items, "OpenF1"),
        (fetch_pdc_items, "PDC"),
    ):
        fetched = fetcher()
        print(f"[INFO] {label}: {len(fetched)} item(s) voor vandaag gevonden.")
        items.extend(fetched)

    selected = dedupe_and_limit(items)
    print(f"[INFO] Geselecteerde bronitems: {len(selected)}")

    for item in selected:
        print(f"[INFO] {item.time} | {item.category} | {item.title} | bron={item.source}")

    return selected


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    try:
        items = build_items()
    except Exception as error:  # pragma: no cover - laatste vangnet voor geldige JSON
        print(f"[WARN] SportAgent viel terug naar lege output: {error}")
        items = []

    payload = build_payload(items)
    save_payload(payload)
    print(f"[DONE] Sportdata opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
