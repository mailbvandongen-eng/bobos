"""Haal nieuws op uit RSS-feeds en schrijf het weg naar data/news.json."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import feedparser


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = ROOT_DIR / "agents" / "news_sources.json"
OUTPUT_PATH = ROOT_DIR / "data" / "news.json"
MAX_ITEMS = 50
MAX_SUMMARY_LENGTH = 220
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


def load_sources() -> list[dict[str, Any]]:
    """Lees de geconfigureerde nieuwsbronnen."""
    with SOURCES_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError("news_sources.json moet een lijst met bronnen bevatten.")

    return data


def fetch_feed_items(source: dict[str, Any]) -> list[dict[str, Any]]:
    """Lees een feed uit en zet entries om naar het BobOS-formaat."""
    source_name = str(source.get("name", "Onbekende bron")).strip()
    source_category = str(source.get("category", "Algemeen")).strip() or "Algemeen"
    feed_url = str(source.get("rss") or source.get("url") or "").strip()

    if not feed_url:
        print(f"[SKIP] {source_name}: geen feed-URL opgegeven.")
        return []

    print(f"[LOAD] {source_name}: {feed_url}")
    feed = feedparser.parse(feed_url)

    if getattr(feed, "bozo", False) and not feed.entries:
        problem = getattr(feed, "bozo_exception", "onbekende feedfout")
        print(f"[SKIP] {source_name}: {problem}")
        return []

    items: list[dict[str, Any]] = []
    feed_language = extract_language(feed.feed)
    skipped_for_language = 0

    for entry in feed.entries:
        url = normalize_url(entry.get("link") or entry.get("id") or "")
        title = clean_text(entry.get("title", ""))
        summary = extract_summary(entry)

        if not url or not title:
            continue

        if not should_keep_entry(entry, title, summary, feed_language):
            skipped_for_language += 1
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
        f"{skipped_for_language} overgeslagen op taal."
    )
    return items


def should_keep_entry(
    entry: dict[str, Any],
    title: str,
    summary: str,
    feed_language: str,
) -> bool:
    """Laat alleen Nederlandstalige items door naar het dashboard."""
    if is_dutch_language(extract_language(entry)):
        return True

    if is_dutch_language(feed_language):
        return True

    combined_text = " ".join(part for part in (title, summary) if part).strip()
    return is_probably_dutch(combined_text)


def extract_language(value: Any) -> str:
    """Lees taal uit feedparser-velden als die beschikbaar zijn."""
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


def is_dutch_language(value: str) -> bool:
    """Controleer of een taalcode wijst op Nederlands."""
    return normalize_language(value).startswith("nl")


def is_probably_dutch(text: str) -> bool:
    """Gebruik simpele Nederlandse stopwoorden als lichte taaltest."""
    words = re.findall(r"[a-zà-ÿ]+", str(text).lower())

    if not words:
        return False

    matches = [word for word in words if word in DUTCH_STOPWORDS]
    unique_matches = set(matches)

    return len(unique_matches) >= 2 or len(matches) >= 3


def extract_summary(entry: dict[str, Any]) -> str:
    """Gebruik summary of description; ontbreekt die, dan blijft het leeg."""
    raw_summary = entry.get("summary") or entry.get("description") or ""
    return limit_text(clean_text(raw_summary), MAX_SUMMARY_LENGTH)


def extract_image(entry: dict[str, Any]) -> str:
    """Zoek een bruikbare afbeelding in veelvoorkomende RSS-velden."""
    candidates: list[str] = []

    for field_name in ("media_thumbnail", "media_content", "enclosures"):
        field_value = entry.get(field_name)
        candidates.extend(extract_urls_from_field(field_value))

    for link in entry.get("links", []):
        if not isinstance(link, dict):
            continue

        link_type = str(link.get("type", "")).lower()
        link_rel = str(link.get("rel", "")).lower()

        if link_type.startswith("image/") or link_rel == "enclosure":
            candidates.extend(extract_urls_from_field(link))

    image_field = entry.get("image")
    candidates.extend(extract_urls_from_field(image_field))

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

    path = urlsplit(value).path.lower()
    image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".svg")

    return path.endswith(image_extensions)


def extract_content_html(value: Any) -> str:
    """Lees HTML uit het feedparser content-veld als dat bestaat."""
    if isinstance(value, list) and value:
        first_item = value[0]
        if isinstance(first_item, dict):
            return str(first_item.get("value", ""))

    return ""


def parse_entry_datetime(entry: dict[str, Any]) -> datetime | None:
    """Zoek een bruikbare publicatiedatum in de feed-entry."""
    parsed_fields = ("published_parsed", "updated_parsed", "created_parsed")
    raw_fields = ("published", "updated", "created")

    for field_name in parsed_fields:
        value = entry.get(field_name)
        if value:
            return datetime(*value[:6], tzinfo=timezone.utc)

    for field_name in raw_fields:
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
            repaired = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

        return repaired

    return value


def dedupe_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verwijder dubbele links en sorteer nieuwste berichten bovenaan."""
    unique_items: dict[str, dict[str, Any]] = {}

    for item in items:
        url = item["url"]
        current = unique_items.get(url)

        if current is None:
            unique_items[url] = item
            continue

        if item["published"] > current["published"]:
            unique_items[url] = item

    sorted_items = sorted(
        unique_items.values(),
        key=sort_key,
        reverse=True,
    )

    return sorted_items[:MAX_ITEMS]


def sort_key(item: dict[str, Any]) -> tuple[int, str]:
    """Sorteer eerst op geldige datum en daarna op datumtekst."""
    published = item.get("published", "")
    return (1 if published else 0, published)


def save_items(items: list[dict[str, Any]]) -> None:
    """Schrijf het resultaat naar data/news.json."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(items, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    sources = load_sources()
    collected_items: list[dict[str, Any]] = []

    for source in sources:
        try:
            collected_items.extend(fetch_feed_items(source))
        except Exception as error:  # pragma: no cover - defensieve feedfoutafhandeling
            source_name = str(source.get("name", "Onbekende bron")).strip()
            print(f"[SKIP] {source_name}: {error}")

    final_items = dedupe_and_sort(collected_items)
    save_items(final_items)
    print(f"[DONE] {len(final_items)} berichten opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
