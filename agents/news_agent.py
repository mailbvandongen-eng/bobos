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
MIN_ITEMS_PER_CATEGORY = {
    "Archeologie": 6,
}
MIN_ITEMS_PER_SOURCE = {
    "Archeologie Online": 2,
    "Historianet": 2,
    "The Past": 2,
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

            keep_result = should_keep_entry(
                entry=entry,
                title=title,
                summary=summary,
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
                    "category": source_category,
                    "image": extract_image(entry),
                    "url": url,
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


def should_keep_entry(
    entry: dict[str, Any],
    title: str,
    summary: str,
    feed_language: str,
    source_category: str,
) -> str:
    """Laat alleen toegestane talen en relevante archeologie-items door."""
    combined_text = " ".join(part for part in (title, summary) if part).strip()
    entry_language = extract_language(entry)

    if entry_language and not is_allowed_language(entry_language, source_category):
        return "language"

    if not entry_language and feed_language and not is_allowed_language(feed_language, source_category):
        return "language"

    if is_archaeology_category(source_category):
        if not (
            is_probably_dutch(combined_text)
            or is_probably_english(combined_text)
            or is_english_language(entry_language)
            or is_english_language(feed_language)
        ):
            return "language"

        if not looks_like_archaeology_story(combined_text):
            return "topic"

        return "keep"

    if entry_language or feed_language:
        return "keep"

    return "keep" if is_probably_dutch(combined_text) else "language"


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
    """Verwijder dubbele links en sorteer nieuwste berichten bovenaan."""
    unique_items: dict[str, dict[str, Any]] = {}

    for item in items:
        url = item["url"]
        current = unique_items.get(url)

        if current is None or item["published"] > current["published"]:
            unique_items[url] = item

    sorted_items = sorted(unique_items.values(), key=sort_key, reverse=True)
    selected_items = sorted_items[:MAX_ITEMS]
    balanced_items = rebalance_category_coverage(selected_items, sorted_items)
    return rebalance_source_coverage(balanced_items, sorted_items)


def rebalance_category_coverage(
    selected_items: list[dict[str, Any]],
    sorted_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bewaar een recente feed, maar reserveer ruimte voor ondervertegenwoordigde categorieen."""
    if not selected_items:
        return selected_items

    protected_minimums = {
        normalize_category(category): minimum
        for category, minimum in MIN_ITEMS_PER_CATEGORY.items()
        if minimum > 0
    }
    if not protected_minimums:
        return selected_items

    balanced = list(selected_items)
    selected_urls = {item["url"] for item in balanced}

    for category, minimum in protected_minimums.items():
        current_count = sum(
            1 for item in balanced if normalize_category(item.get("category", "")) == category
        )
        if current_count >= minimum:
            continue

        extras = [
            item
            for item in sorted_items
            if item["url"] not in selected_urls
            and normalize_category(item.get("category", "")) == category
        ][: minimum - current_count]

        for item in extras:
            balanced.append(item)
            selected_urls.add(item["url"])

    while len(balanced) > MAX_ITEMS:
        removal_index = find_removable_index(balanced, protected_minimums, {})
        if removal_index is None:
            break
        balanced.pop(removal_index)

    return balanced[:MAX_ITEMS]


def rebalance_source_coverage(
    selected_items: list[dict[str, Any]],
    sorted_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bewaar ook bronspreiding voor archeologie, zodat de categorie niet op een feed leunt."""
    if not selected_items:
        return selected_items

    protected_categories = {
        normalize_category(category): minimum
        for category, minimum in MIN_ITEMS_PER_CATEGORY.items()
        if minimum > 0
    }
    protected_sources = {
        normalize_source_name(source): minimum
        for source, minimum in MIN_ITEMS_PER_SOURCE.items()
        if minimum > 0
    }
    if not protected_sources:
        return selected_items

    balanced = list(selected_items)
    selected_urls = {item["url"] for item in balanced}

    for source_name, minimum in protected_sources.items():
        current_count = sum(
            1 for item in balanced if normalize_source_name(item.get("source", "")) == source_name
        )
        if current_count >= minimum:
            continue

        extras = [
            item
            for item in sorted_items
            if item["url"] not in selected_urls
            and normalize_source_name(item.get("source", "")) == source_name
        ][: minimum - current_count]

        for item in extras:
            balanced.append(item)
            selected_urls.add(item["url"])

    while len(balanced) > MAX_ITEMS:
        removal_index = find_removable_index(balanced, protected_categories, protected_sources)
        if removal_index is None:
            break
        balanced.pop(removal_index)

    return balanced[:MAX_ITEMS]


def find_removable_index(
    items: list[dict[str, Any]],
    protected_minimums: dict[str, int],
    protected_sources: dict[str, int],
) -> int | None:
    """Verwijder bij voorkeur de oudste items buiten beschermde minima."""
    category_counts = Counter(
        normalize_category(item.get("category", ""))
        for item in items
    )
    source_counts = Counter(
        normalize_source_name(item.get("source", ""))
        for item in items
    )

    for index in range(len(items) - 1, -1, -1):
        category = normalize_category(items[index].get("category", ""))
        source_name = normalize_source_name(items[index].get("source", ""))
        category_minimum = protected_minimums.get(category, 0)
        source_minimum = protected_sources.get(source_name, 0)
        if category_counts[category] > category_minimum and source_counts[source_name] > source_minimum:
            return index

    return None


def sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """Sorteer eerst op geldige datum en daarna op datumtekst."""
    published = item.get("published", "")
    return (1 if published else 0, published)


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
