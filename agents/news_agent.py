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
    feed_url = str(source.get("url", "")).strip()

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

    for entry in feed.entries:
        url = normalize_url(entry.get("link") or entry.get("id") or "")
        title = clean_text(entry.get("title", ""))

        if not url or not title:
            continue

        items.append(
            {
                "title": title,
                "summary": extract_summary(entry),
                "source": source_name,
                "published": format_datetime(parse_entry_datetime(entry)),
                "url": url,
            }
        )

    print(f"[OK] {source_name}: {len(items)} berichten gevonden.")
    return items


def extract_summary(entry: dict[str, Any]) -> str:
    """Gebruik summary of description; ontbreekt die, dan blijft het leeg."""
    raw_summary = entry.get("summary") or entry.get("description") or ""
    return clean_text(raw_summary)


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


def repair_mojibake(value: str) -> str:
    """Herstel veelvoorkomende UTF-8/Latin-1-verwisselingen uit feeds."""
    suspicious_markers = ("Ã", "Â", "â€", "â€™", "â€œ", "â€", "â€¦")

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
