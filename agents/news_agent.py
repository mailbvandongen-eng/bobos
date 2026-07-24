"""Haal BobOS-nieuws op en schrijf het weg naar data/news.json."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import feedparser

from json_store import load_json, save_json_if_changed


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT_DIR / "agents" / "news_sources.json"
OUTPUT_PATH = ROOT_DIR / "data" / "news.json"
MAX_ITEMS = 120
MAX_SUMMARY_LENGTH = 220
USER_AGENT = "Mozilla/5.0 (compatible; BobOS NewsAgent/0.3)"
TARGET_CATEGORY_ORDER = (
    "Tech",
    "Archeologie",
    "Wetenschap",
    "Gadgets",
    "Voetbal",
)
CATEGORY_TARGETS = {
    "Tech": 24,
    "Archeologie": 22,
    "Wetenschap": 22,
    "Gadgets": 22,
    "Voetbal": 30,
}
CATEGORY_MAX_ITEMS = {
    "Tech": 30,
    "Archeologie": 28,
    "Wetenschap": 28,
    "Gadgets": 28,
    "Voetbal": 40,
}
SOURCE_PRIORITY = {
    "tweakers": 42,
    "scientias": 38,
    "archeologie online": 36,
    "rijksdienst voor het cultureel erfgoed": 35,
    "historianet": 34,
    "the past": 32,
    "national geographic nederland": 30,
    "nos algemeen": 28,
    "nos sport": 26,
    "voetbal international": 24,
    "bright": 18,
    "voetbalprimeur": 10,
}
DUTCH_WORD_PATTERN = re.compile(r"[a-z\u00e0-\u00ff]+")
DUTCH_STOPWORDS = {
    "aan",
    "als",
    "bij",
    "dan",
    "dat",
    "de",
    "deze",
    "door",
    "een",
    "en",
    "het",
    "met",
    "na",
    "naar",
    "niet",
    "nog",
    "om",
    "ook",
    "op",
    "over",
    "te",
    "tot",
    "uit",
    "van",
    "voor",
    "wordt",
    "zijn",
}
ENGLISH_STOPWORDS = {
    "a",
    "after",
    "and",
    "are",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "new",
    "of",
    "on",
    "that",
    "the",
    "this",
    "to",
    "with",
}
ARCHAEOLOGY_KEYWORDS = (
    "ancient dna",
    "archaeolog",
    "artefact",
    "artifact",
    "archeolog",
    "bronstijd",
    "burial",
    "dekzand",
    "dna-onderzoek",
    "early human",
    "erfgoed",
    "excavation",
    "fossiele",
    "grafveld",
    "grave",
    "ijzertijd",
    "neanderthal",
    "neanderthaler",
    "oeverwal",
    "opgraving",
    "prehistor",
    "rivierduin",
    "romeins",
    "skeleton",
    "skelet",
    "steentijd",
    "stroomrug",
    "urnenveld",
    "vondst",
)
SCIENCE_KEYWORDS = (
    "astronomie",
    "bacterie",
    "biologie",
    "brein",
    "cel",
    "climate",
    "dna",
    "evolutie",
    "gen",
    "genoom",
    "klimaat",
    "mars",
    "natuur",
    "onderzoek",
    "opwarming",
    "planeet",
    "ruimte",
    "satelliet",
    "science",
    "studie",
    "universum",
    "wetenschap",
)
TECH_KEYWORDS = (
    "ai",
    "api",
    "app",
    "beveilig",
    "chip",
    "cloud",
    "data",
    "datacenter",
    "eu",
    "internet",
    "ios",
    "linux",
    "microsoft",
    "open source",
    "openai",
    "privacy",
    "server",
    "software",
    "sms",
    "telecom",
    "update",
    "vodafone",
)
GADGET_KEYWORDS = (
    "camera",
    "console",
    "controller",
    "e-bike",
    "fiets",
    "gadget",
    "gameconsole",
    "headset",
    "hp ",
    "iphone",
    "kindle",
    "laptop",
    "monitor",
    "nothing",
    "omnibook",
    "playstation",
    "nintendo",
    "notitieblok",
    "oled",
    "phone",
    "pixel",
    "robot",
    "smartphone",
    "switch",
    "tablet",
    "telefoon",
    "wearable",
    "xbox",
    "xtool",
    "yubikey",
)
FOOTBALL_GENERAL_KEYWORDS = (
    "ajax",
    "arsenal",
    "barcelona",
    "bayern",
    "chelsea",
    "eredivisie",
    "feyenoord",
    "football",
    "lfc",
    "liverpool",
    "manchester city",
    "manchester united",
    "man utd",
    "oranje",
    "premier league",
    "psv",
    "voetbal",
    "wk",
)
FOOTBALL_FOCUS_KEYWORDS = (
    "ajax",
    "psv",
    "feyenoord",
    "manchester united",
    "man utd",
    "barcelona",
    "fc barcelona",
    "bayern",
    "bayern munchen",
    "bayern münchen",
    "premier league",
    "arsenal",
    "chelsea",
    "lfc",
    "liverpool",
    "manchester city",
    "newcastle",
    "tottenham",
    "the reds",
)
LOW_VALUE_URL_FRAGMENTS = (
    "/video/",
    "/videos/",
    "/live-",
    "/live/",
    "/podcast/",
)
GENERIC_LOW_VALUE_TITLE_KEYWORDS = (
    ".geek -",
    "alle ontwikkelingen",
    "live ",
    "live:",
    "podcast",
    "round-up",
    "software-update -",
    "wekdienst",
)
FOOTBALL_LOW_VALUE_KEYWORDS = (
    "derksen",
    "dijkshoorn",
    "familie",
    "hartverscheurend",
    "helden",
    "instagram",
    "neefjes",
    "oorlogsvoetbal",
    "overlijden",
    "roddel",
    "schandaal",
    "schrikt",
    "social media",
    "van der gijp",
    "vriend'",
    "vriend ",
)
GADGET_CLICKBAIT_KEYWORDS = (
    ".geek",
    "fascinerende",
    "gaat op het punt",
    "het beste",
    "niet meer naar",
    "nooit meer",
    "raad het",
    "waarom je",
)
SCIENCE_LOW_VALUE_KEYWORDS = (
    "seksleven",
)
HTML_FEED_LINK_PATTERN = re.compile(
    r"""href=["']([^"']+)["'][^>]+type=["'](?:application/(?:rss|atom)\+xml|application/xml|text/xml)["']
    |type=["'](?:application/(?:rss|atom)\+xml|application/xml|text/xml)["'][^>]+href=["']([^"']+)["']""",
    re.IGNORECASE | re.VERBOSE,
)
INLINE_FEED_URL_PATTERN = re.compile(r"https?://[^\"'\s>]+(?:rss|feed)[^\"'\s<]*", re.IGNORECASE)


def load_sources() -> list[dict[str, Any]]:
    """Lees de geconfigureerde nieuwsbronnen."""
    with SOURCES_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("news_sources.json moet een lijst met bronnen bevatten.")

    return payload


def fetch_feed_items(source: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    """Lees een bron uit en zet entries om naar het BobOS-formaat."""
    source_name = str(source.get("name", "Onbekende bron")).strip()
    source_category = str(source.get("category", "Algemeen")).strip() or "Algemeen"
    feed_urls = discover_source_feed_urls(source)

    if not feed_urls:
        print(f"[SKIP] {source_name}: geen feed-URL opgegeven.")
        return [], False

    reachable = False
    last_problem = "geen bruikbare feed gevonden"

    for feed_url in feed_urls:
        print(f"[LOAD] {source_name}: {feed_url}")
        feed = feedparser.parse(feed_url, agent=USER_AGENT)

        if getattr(feed, "bozo", False) and not feed.entries:
            last_problem = str(getattr(feed, "bozo_exception", "onbekende feedfout"))
            continue

        reachable = True

        if not feed.entries:
            last_problem = "lege feed of HTML-overzicht zonder items"
            continue

        items: list[dict[str, Any]] = []
        feed_language = extract_language(feed.feed)
        skipped_for_language = 0
        skipped_for_topic = 0

        for entry in feed.entries:
            url = normalize_url(entry.get("link") or entry.get("id") or "")
            title = clean_text(entry.get("title", ""))
            summary = extract_summary(entry)

            if not url or not title:
                continue

            keep_result, output_category, priority = classify_entry(
                entry=entry,
                source_name=source_name,
                title=title,
                summary=summary,
                url=url,
                feed_language=feed_language,
                source_category=source_category,
            )
            if keep_result == "language":
                skipped_for_language += 1
                continue

            if keep_result == "topic":
                skipped_for_topic += 1
                continue

            items.append(
                {
                    "title": title,
                    "summary": summary,
                    "source": source_name,
                    "published": format_datetime(parse_entry_datetime(entry)),
                    "category": output_category,
                    "image": extract_image(entry),
                    "url": url,
                    "_priority": priority,
                }
            )

        print(
            f"[OK] {source_name}: {len(items)} berichten gevonden, "
            f"{skipped_for_language} overgeslagen op taal, "
            f"{skipped_for_topic} op onderwerp."
        )
        return items, True

    if reachable:
        print(f"[OK] {source_name}: bron bereikbaar, maar geen bruikbare items na filtering.")
        return [], True

    print(f"[SKIP] {source_name}: {last_problem}")
    return [], False


def classify_entry(
    entry: dict[str, Any],
    source_name: str,
    title: str,
    summary: str,
    url: str,
    feed_language: str,
    source_category: str,
) -> tuple[str, str, int]:
    """Bepaal of een item bruikbaar is, inclusief categorie en prioriteit."""
    combined_text = " ".join(part for part in (title, summary) if part).strip()
    entry_language = extract_language(entry)

    if entry_language and not is_allowed_language(entry_language, source_category):
        return "language", "", 0

    if not entry_language and feed_language and not is_allowed_language(feed_language, source_category):
        return "language", "", 0

    output_category = resolve_output_category(
        source_name=source_name,
        source_category=source_category,
        title=title,
        summary=summary,
        url=url,
    )
    if not output_category:
        return "topic", "", 0

    if is_archaeology_category(source_category):
        if not (
            is_probably_dutch(combined_text)
            or is_probably_english(combined_text)
            or is_english_language(entry_language)
            or is_english_language(feed_language)
        ):
            return "language", "", 0

        if not looks_like_archaeology_story(combined_text):
            return "topic", "", 0

    elif entry_language or feed_language:
        if not (
            is_dutch_language(entry_language)
            or is_dutch_language(feed_language)
            or (
                normalize_category(output_category) == "archeologie"
                and (
                    is_english_language(entry_language)
                    or is_english_language(feed_language)
                    or is_probably_english(combined_text)
                )
            )
        ):
            return "language", "", 0

    elif normalize_category(output_category) == "archeologie":
        if not (is_probably_dutch(combined_text) or is_probably_english(combined_text)):
            return "language", "", 0

    elif not is_probably_dutch(combined_text):
        return "language", "", 0

    if is_low_value_story(
        source_name=source_name,
        output_category=output_category,
        title=title,
        summary=summary,
        url=url,
    ):
        return "topic", "", 0

    priority = compute_item_priority(
        source_name=source_name,
        output_category=output_category,
        title=title,
        summary=summary,
    )
    return "keep", output_category, priority


def resolve_output_category(
    *,
    source_name: str,
    source_category: str,
    title: str,
    summary: str,
    url: str,
) -> str:
    """Map bron- en inhoudssignalen naar de gewenste BobOS-categorieen."""
    normalized_source = normalize_source_name(source_name)
    normalized_category = normalize_category(source_category)
    combined_text = " ".join(part for part in (title, summary, url) if part).strip().lower()

    if normalized_category == "archeologie":
        return "Archeologie" if looks_like_archaeology_story(combined_text) else ""

    if normalized_category == "wetenschap":
        return "Wetenschap" if looks_like_science_story(combined_text) else ""

    if normalized_category == "voetbal":
        return "Voetbal" if looks_like_football_story(combined_text) else ""

    if normalized_category == "gadgets":
        if normalized_source == "tweakers":
            return "Gadgets" if looks_like_gadget_story(combined_text) else "Tech"
        return "Gadgets" if looks_like_gadget_story(combined_text) else "Tech" if looks_like_tech_story(combined_text) else ""

    if normalized_category == "sport":
        return "Voetbal" if looks_like_football_story(combined_text) else ""

    if normalized_category in {"algemeen", "musea"}:
        if looks_like_archaeology_story(combined_text):
            return "Archeologie"
        if looks_like_science_story(combined_text):
            return "Wetenschap"
        if looks_like_football_story(combined_text):
            return "Voetbal"
        if looks_like_gadget_story(combined_text):
            return "Gadgets"
        if looks_like_tech_story(combined_text):
            return "Tech"

    return ""


def looks_like_science_story(text: str) -> bool:
    """Herken wetenschapsverhalen grofmazig op inhoudssignalen."""
    lowered = str(text or "").lower()
    return contains_any_keyword(lowered, SCIENCE_KEYWORDS)


def looks_like_tech_story(text: str) -> bool:
    """Herken techverhalen die meer over platformen, software of infra gaan."""
    lowered = str(text or "").lower()
    return contains_any_keyword(lowered, TECH_KEYWORDS)


def looks_like_gadget_story(text: str) -> bool:
    """Herken gadgetverhalen die draaien om apparaten en consumentenhardware."""
    lowered = str(text or "").lower()
    if contains_any_keyword(lowered, GADGET_KEYWORDS):
        return True

    return lowered.startswith("quicktest -") and not contains_any_keyword(
        lowered,
        ("chip", "cpu", "gpu", "datacenter", "server", "epyc", "instinct"),
    )


def looks_like_football_story(text: str) -> bool:
    """Herken voetbalverhalen via club-, competitie- en sporttermen."""
    lowered = str(text or "").lower()
    return contains_any_keyword(lowered, FOOTBALL_GENERAL_KEYWORDS)


def contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    """Controleer of een van de opgegeven termen voorkomt in tekst."""
    lowered = str(text or "").lower()
    return any(keyword_in_text(lowered, keyword) for keyword in keywords)


def keyword_in_text(text: str, keyword: str) -> bool:
    """Match keywords woordbewust zodat korte termen geen ruis veroorzaken."""
    lowered_text = str(text or "").lower()
    lowered_keyword = str(keyword or "").strip().lower()
    if not lowered_keyword:
        return False

    pattern = rf"(?<![a-z0-9]){re.escape(lowered_keyword)}(?![a-z0-9])"
    return re.search(pattern, lowered_text) is not None


def is_low_value_story(
    *,
    source_name: str,
    output_category: str,
    title: str,
    summary: str,
    url: str,
) -> bool:
    """Filter clickbait, liveblogs, roddel en andere lage-signaalitems."""
    lowered_title = str(title or "").lower()
    lowered_summary = str(summary or "").lower()
    lowered_url = str(url or "").lower()
    combined_text = f"{lowered_title} {lowered_summary}".strip()
    normalized_source = normalize_source_name(source_name)
    normalized_category = normalize_category(output_category)

    if any(fragment in lowered_url for fragment in LOW_VALUE_URL_FRAGMENTS):
        return True

    if contains_any_keyword(lowered_title, GENERIC_LOW_VALUE_TITLE_KEYWORDS):
        return True

    if normalized_category == "voetbal":
        if contains_any_keyword(combined_text, FOOTBALL_LOW_VALUE_KEYWORDS):
            return True
        if "reageert op" in combined_text and football_relevance_score(combined_text) == 0:
            return True
        if normalized_source == "voetbalprimeur" and football_relevance_score(combined_text) == 0:
            return True

    if normalized_category == "gadgets" and normalized_source == "bright":
        if contains_any_keyword(lowered_title, GADGET_CLICKBAIT_KEYWORDS):
            return True

    if normalized_category == "wetenschap" and contains_any_keyword(combined_text, SCIENCE_LOW_VALUE_KEYWORDS):
        return True

    if normalized_category == "archeologie":
        if re.search(r"\bcurrent archaeology\s+\d+\b", lowered_title):
            return True
        if "war graves commission memorial" in combined_text:
            return True

    return False


def football_relevance_score(text: str) -> int:
    """Geef hogere scores aan de expliciete voetbalfocus van BobOS."""
    lowered = str(text or "").lower()
    score = 0

    for keyword in FOOTBALL_FOCUS_KEYWORDS:
        if keyword in lowered:
            score += 18

    if "eredivisie" in lowered:
        score += 8
    if "champions league" in lowered or "europa league" in lowered:
        score += 6
    if "transfer" in lowered or "contract" in lowered or "coach" in lowered:
        score += 4

    return score


def compute_item_priority(
    *,
    source_name: str,
    output_category: str,
    title: str,
    summary: str,
) -> int:
    """Bereken een pragmatische prioriteit voor selectie en deduplicatie."""
    normalized_source = normalize_source_name(source_name)
    normalized_category = normalize_category(output_category)
    combined_text = " ".join(part for part in (title, summary) if part).strip().lower()
    score = SOURCE_PRIORITY.get(normalized_source, 0)

    if normalized_category == "voetbal":
        score += football_relevance_score(combined_text)
    elif normalized_category == "archeologie":
        score += 18 if contains_any_keyword(combined_text, ("steentijd", "opgraving", "romeins", "ancient dna", "neanderthal")) else 10
    elif normalized_category == "wetenschap":
        score += 16 if contains_any_keyword(combined_text, ("ruimte", "klimaat", "dna", "onderzoek", "planeet")) else 9
    elif normalized_category == "tech":
        score += 14 if contains_any_keyword(combined_text, ("openai", "apple", "microsoft", "datacenter", "telecom", "beveilig")) else 8
    elif normalized_category == "gadgets":
        score += 12 if contains_any_keyword(combined_text, ("iphone", "switch", "laptop", "camera", "robot", "tablet")) else 6

    return score


def extract_language(value: Any) -> str:
    """Lees een taalcode uit feedparser-velden."""
    if isinstance(value, dict):
        for field_name in ("language", "lang", "dc_language"):
            field_value = value.get(field_name)
            if field_value:
                return normalize_language(field_value)

    if isinstance(value, str):
        return normalize_language(value)

    return ""


def normalize_language(value: Any) -> str:
    """Zet taalwaarden om naar een klein, vergelijkbaar formaat."""
    return str(value or "").strip().lower().replace("_", "-")


def normalize_category(value: str) -> str:
    """Maak categoriewaarden vergelijkbaar."""
    return str(value or "").strip().lower()


def normalize_source_name(value: str) -> str:
    """Maak bronnamen vergelijkbaar."""
    return str(value or "").strip().lower()


def is_dutch_language(value: str) -> bool:
    """Controleer of een taalcode wijst op Nederlands."""
    return normalize_language(value).startswith("nl")


def is_english_language(value: str) -> bool:
    """Controleer of een taalcode wijst op Engels."""
    return normalize_language(value).startswith("en")


def is_archaeology_category(value: str) -> bool:
    """Controleer of een bron onder archeologie valt."""
    return normalize_category(value) == "archeologie"


def is_allowed_language(value: str, source_category: str) -> bool:
    """Sta Nederlands altijd toe en Engels alleen voor archeologie."""
    if is_dutch_language(value):
        return True

    return is_archaeology_category(source_category) and is_english_language(value)


def is_probably_dutch(text: str) -> bool:
    """Gebruik simpele Nederlandse stopwoorden als lichte taaltest."""
    words = DUTCH_WORD_PATTERN.findall(str(text).lower())

    if not words:
        return False

    matches = [word for word in words if word in DUTCH_STOPWORDS]
    return len(set(matches)) >= 2 or len(matches) >= 3


def is_probably_english(text: str) -> bool:
    """Gebruik simpele Engelse stopwoorden als lichte taaltest."""
    words = DUTCH_WORD_PATTERN.findall(str(text).lower())

    if not words:
        return False

    matches = [word for word in words if word in ENGLISH_STOPWORDS]
    return len(set(matches)) >= 2 or len(matches) >= 3


def looks_like_archaeology_story(text: str) -> bool:
    """Laat archeologiebronnen alleen door bij duidelijke archeologie-signalen."""
    lowered = str(text or "").lower()
    return any(keyword in lowered for keyword in ARCHAEOLOGY_KEYWORDS)


def discover_source_feed_urls(source: dict[str, Any]) -> list[str]:
    """Verzamel directe en via HTML ontdekte feed-URLs voor een bron."""
    discovered: list[str] = []

    direct_url = str(source.get("rss") or "").strip()
    source_url = str(source.get("url") or "").strip()

    if direct_url:
        discovered.append(normalize_url(direct_url))

    if source_url:
        normalized_source_url = normalize_url(source_url)
        if looks_like_feed_url(normalized_source_url):
            discovered.append(normalize_url(normalized_source_url))
        discovered.extend(discover_feed_urls_from_page(normalized_source_url))

    return dedupe_urls(discovered)


def looks_like_feed_url(value: str) -> bool:
    """Herken directe RSS-, Atom- of XML-feed-URLs grofmazig."""
    lowered = str(value or "").lower()
    return lowered.endswith((".xml", ".rss", ".atom")) or "/feed" in lowered or "rss" in lowered


def discover_feed_urls_from_page(page_url: str) -> list[str]:
    """Zoek RSS- of Atom-links op een HTML-pagina."""
    try:
        request = Request(page_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=20) as response:
            raw_bytes = response.read()
    except Exception:
        return []

    html = raw_bytes.decode("utf-8", errors="replace")
    lowered = html.lower()
    if "<rss" in lowered or "<feed" in lowered:
        return [normalize_url(page_url)]

    candidates: list[str] = []

    for match in HTML_FEED_LINK_PATTERN.finditer(html):
        href = match.group(1) or match.group(2) or ""
        if href:
            candidates.append(normalize_url(urljoin(page_url, href)))

    for url in INLINE_FEED_URL_PATTERN.findall(html):
        candidates.append(normalize_url(urljoin(page_url, url)))

    return dedupe_urls(candidates)


def dedupe_urls(urls: list[str]) -> list[str]:
    """Verwijder lege of dubbele URLs en bewaar de volgorde."""
    seen: set[str] = set()
    result: list[str] = []

    for url in urls:
        normalized = normalize_url(url)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)

    return result


def extract_summary(entry: dict[str, Any]) -> str:
    """Gebruik summary of description; ontbreekt die, dan blijft het leeg."""
    raw_summary = entry.get("summary") or entry.get("description") or ""
    return limit_text(clean_text(raw_summary), MAX_SUMMARY_LENGTH)


def extract_image(entry: dict[str, Any]) -> str:
    """Zoek een bruikbare afbeelding in veelvoorkomende RSS-velden."""
    candidates: list[str] = []

    for field_name in ("media_thumbnail", "media_content", "enclosures"):
        candidates.extend(extract_urls_from_field(entry.get(field_name)))

    for link in entry.get("links", []):
        if not isinstance(link, dict):
            continue

        link_type = str(link.get("type", "")).lower()
        link_rel = str(link.get("rel", "")).lower()
        if link_type.startswith("image/") or link_rel == "enclosure":
            candidates.extend(extract_urls_from_field(link))

    candidates.extend(extract_urls_from_field(entry.get("image")))

    html_candidates = (
        entry.get("summary")
        or entry.get("description")
        or extract_content_html(entry.get("content"))
    )
    candidates.extend(extract_image_urls_from_html(str(html_candidates)))

    for candidate in candidates:
        normalized = normalize_url(candidate)
        if is_probable_image_url(normalized):
            return normalized

    return ""


def extract_urls_from_field(value: Any) -> list[str]:
    """Lees mogelijke afbeeldings-URLs uit lijst-, dict- of stringvelden."""
    urls: list[str] = []

    if isinstance(value, list):
        for item in value:
            urls.extend(extract_urls_from_field(item))
        return urls

    if isinstance(value, dict):
        for key in ("url", "href"):
            field_value = value.get(key)
            if field_value:
                urls.append(str(field_value))
        return urls

    if isinstance(value, str) and value.strip():
        urls.append(value.strip())

    return urls


def extract_image_urls_from_html(value: str) -> list[str]:
    """Zoek simpele img-src waarden in HTML-fragmenten."""
    pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    return pattern.findall(value)


def is_probable_image_url(value: str) -> bool:
    """Voorkom dat artikel-URLs per ongeluk als afbeelding worden opgeslagen."""
    if not (value.startswith("http://") or value.startswith("https://")):
        return False

    return urlsplit(value).path.lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")
    )


def extract_content_html(value: Any) -> str:
    """Lees HTML uit het feedparser content-veld als dat bestaat."""
    if isinstance(value, list) and value:
        first_item = value[0]
        if isinstance(first_item, dict):
            return str(first_item.get("value", ""))

    return ""


def parse_entry_datetime(entry: dict[str, Any]) -> datetime | None:
    """Zoek een bruikbare publicatiedatum in de feed-entry."""
    for field_name in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(field_name)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)

    for field_name in ("published", "updated", "created"):
        raw_value = entry.get(field_name)
        if not raw_value:
            continue

        try:
            parsed = parsedate_to_datetime(str(raw_value))
        except (TypeError, ValueError, IndexError):
            continue

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    return None


def format_datetime(value: datetime | None) -> str:
    """Zet een datum om naar een JSON-vriendelijke ISO-notatie."""
    if value is None:
        return ""

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_url(value: str) -> str:
    """Maak URLs consistenter voor deduplicatie."""
    url = str(value).strip()
    if not url:
        return ""

    parts = urlsplit(url)
    cleaned = parts._replace(fragment="")
    return urlunsplit(cleaned)


def clean_text(value: str) -> str:
    """Verwijder HTML en zet witruimte om naar gewone leesbare tekst."""
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = unescape(text)
    text = repair_mojibake(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def limit_text(value: str, max_length: int) -> str:
    """Maak samenvattingen compact zonder midden in een woord te breken."""
    text = str(value).strip()

    if len(text) <= max_length:
        return text

    shortened = text[:max_length].rsplit(" ", 1)[0].strip()
    return f"{shortened}..."


def repair_mojibake(value: str) -> str:
    """Herstel veelvoorkomende UTF-8/Latin-1-verwisselingen uit feeds."""
    suspicious_markers = (
        "\u00c3",
        "\u00c2",
        "\u00e2\u20ac",
        "\u00e2\u20ac\u2122",
        "\u00e2\u20ac\u0153",
        "\u00e2\u20ac\u009d",
        "\u00e2\u20ac\u00a6",
    )

    if not any(marker in value for marker in suspicious_markers):
        return value

    for encoding in ("cp1252", "latin-1"):
        try:
            return value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

    return value


def dedupe_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupeer items en bouw daarna een gebalanceerde categorie-selectie."""
    unique_items: dict[str, dict[str, Any]] = {}

    for item in items:
        url = item["url"]
        current = unique_items.get(url)

        if current is None or compare_item_priority(item, current):
            unique_items[url] = item

    ranked_items = sorted(unique_items.values(), key=sort_key, reverse=True)
    selected_items = select_balanced_items(ranked_items)
    return [strip_internal_fields(item) for item in selected_items]


def compare_item_priority(candidate: dict[str, Any], current: dict[str, Any]) -> bool:
    """Kies bij dubbele URLs het item met de sterkste prioriteit en recentste datum."""
    candidate_priority = int(candidate.get("_priority", 0))
    current_priority = int(current.get("_priority", 0))

    if candidate_priority != current_priority:
        return candidate_priority > current_priority

    return str(candidate.get("published", "")) > str(current.get("published", ""))


def select_balanced_items(ranked_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verdeel de feed expliciet over de gewenste categorieen."""
    if not ranked_items:
        return []

    normalized_targets = {
        normalize_category(category): minimum
        for category, minimum in CATEGORY_TARGETS.items()
        if minimum > 0
    }
    normalized_maxima = {
        normalize_category(category): maximum
        for category, maximum in CATEGORY_MAX_ITEMS.items()
        if maximum > 0
    }
    buckets = {normalize_category(category): [] for category in TARGET_CATEGORY_ORDER}

    for item in ranked_items:
        category = normalize_category(item.get("category", ""))
        if category in buckets:
            buckets[category].append(item)

    selected: list[dict[str, Any]] = []
    selected_urls: set[str] = set()
    category_counts: Counter[str] = Counter()

    for category_name in TARGET_CATEGORY_ORDER:
        normalized_category = normalize_category(category_name)
        target = normalized_targets.get(normalized_category, 0)

        for item in buckets.get(normalized_category, []):
            if category_counts[normalized_category] >= target or len(selected) >= MAX_ITEMS:
                break
            selected.append(item)
            selected_urls.add(item["url"])
            category_counts[normalized_category] += 1

    remaining_items = [
        item
        for item in ranked_items
        if item["url"] not in selected_urls and normalize_category(item.get("category", "")) in buckets
    ]

    for item in remaining_items:
        if len(selected) >= MAX_ITEMS:
            break

        category = normalize_category(item.get("category", ""))
        if category_counts[category] >= normalized_maxima.get(category, MAX_ITEMS):
            continue

        selected.append(item)
        selected_urls.add(item["url"])
        category_counts[category] += 1

    if len(selected) < MAX_ITEMS:
        for item in remaining_items:
            if len(selected) >= MAX_ITEMS:
                break
            if item["url"] in selected_urls:
                continue
            selected.append(item)
            selected_urls.add(item["url"])

    return sorted(selected, key=sort_key, reverse=True)


def strip_internal_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Haal interne selectievelden uit het JSON-resultaat."""
    return {
        key: value
        for key, value in item.items()
        if not key.startswith("_")
    }


def sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """Sorteer op prioriteit en daarna op datum."""
    published = item.get("published", "")
    return (int(item.get("_priority", 0)), 1 if published else 0, published)


def save_items(items: list[dict[str, Any]]) -> bool:
    """Schrijf het resultaat naar data/news.json als de inhoud is gewijzigd."""
    return save_json_if_changed(OUTPUT_PATH, items)


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    collected_items: list[dict[str, Any]] = []
    reachable_sources = 0

    try:
        sources = load_sources()
    except Exception as error:  # pragma: no cover
        print(f"[WARN] Kon bronnen niet laden: {error}")
        changed = save_items([])
        print(
            f"[DONE] 0 berichten gecontroleerd in {OUTPUT_PATH} "
            f"({'gewijzigd' if changed else 'ongewijzigd'})."
        )
        return

    for source in sources:
        try:
            source_items, reachable = fetch_feed_items(source)
            collected_items.extend(source_items)
            if reachable:
                reachable_sources += 1
        except Exception as error:  # pragma: no cover
            source_name = str(source.get("name", "Onbekende bron")).strip()
            print(f"[SKIP] {source_name}: {error}")

    if reachable_sources == 0:
        current_payload = load_json(OUTPUT_PATH)
        if isinstance(current_payload, list):
            print(
                f"[DONE] Geen feeds bereikbaar; bestaand {OUTPUT_PATH} blijft staan "
                "(ongewijzigd)."
            )
            return

    final_items = dedupe_and_sort(collected_items)
    changed = save_items(final_items)
    print(
        f"[DONE] {len(final_items)} berichten gecontroleerd in {OUTPUT_PATH} "
        f"({'gewijzigd' if changed else 'ongewijzigd'})."
    )


if __name__ == "__main__":
    main()
