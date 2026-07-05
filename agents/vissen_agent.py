"""Schrijf voorbeelddata voor het visdomein van BobOS v0.2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "vissen.json"
VISSEN_URL = "https://mailbvandongen-eng.github.io/visapp/"


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_items() -> list[dict[str, str]]:
    """Geef drie simpele voorbeeldregels terug voor vissen."""
    return [
        {"label": "Wind", "value": "ZW 3 Bft"},
        {"label": "Luchtdruk", "value": "Stabiel"},
        {"label": "Conclusie", "value": "Redelijke avond"},
    ]


def build_payload() -> dict[str, object]:
    """Maak een geldige JSON-structuur voor de vistegel."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Viskansen vandaag",
        "items": build_items(),
        "url": VISSEN_URL,
    }


def save_payload(payload: dict[str, object]) -> None:
    """Schrijf het JSON-bestand altijd netjes weg."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    """Hoofdroute voor lokaal gebruik en GitHub Actions."""
    payload = build_payload()
    save_payload(payload)
    print(f"[DONE] Visdata opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
