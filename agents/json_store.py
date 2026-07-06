"""Helpers voor stabiele JSON-output in agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_json(path: Path) -> Any | None:
    """Lees bestaand JSON in als het bestand aanwezig en geldig is."""
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def normalize_for_compare(value: Any, ignored_keys: set[str]) -> Any:
    """Verwijder vluchtige sleutels recursief voor een semantische vergelijking."""
    if isinstance(value, dict):
        return {
            key: normalize_for_compare(child, ignored_keys)
            for key, child in sorted(value.items())
            if key not in ignored_keys
        }

    if isinstance(value, list):
        return [normalize_for_compare(child, ignored_keys) for child in value]

    return value


def save_json_if_changed(
    path: Path,
    payload: Any,
    *,
    ignored_keys: Iterable[str] = (),
) -> bool:
    """Schrijf JSON alleen weg als de inhoud inhoudelijk is gewijzigd."""
    ignored = set(ignored_keys)
    current_payload = load_json(path)

    if current_payload is not None:
        current_normalized = normalize_for_compare(current_payload, ignored)
        next_normalized = normalize_for_compare(payload, ignored)

        if current_normalized == next_normalized:
            return False

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return True
