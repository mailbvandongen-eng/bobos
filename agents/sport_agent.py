"""Schrijf voorbeelddata voor het sportdomein van BobOS v0.2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "sport.json"
SPORT_URL = "https://mailbvandongen-eng.github.io/sport-op-tv/"


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_items() -> list[dict[str, str]]:
    """Geef drie voorbeelditems terug voor BobOS v0.2."""
    schedule = [
        {"time": "18:30", "title": "Formule 1 Weekend Update", "category": "Formule 1", "url": SPORT_URL},
        {"time": "20:00", "title": "Premier League Darts", "category": "Darts", "url": SPORT_URL},
        {"time": "21:00", "title": "Avondwedstrijd Voetbal", "category": "Voetbal", "url": SPORT_URL},
    ]
    return schedule[:3]


def build_payload() -> dict[str, object]:
    """Maak een geldige JSON-structuur voor de sporttegel."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Sport op TV vandaag",
        "items": build_items(),
        "url": SPORT_URL,
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
    print(f"[DONE] Sportdata opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
