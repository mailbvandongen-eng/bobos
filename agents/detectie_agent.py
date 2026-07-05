"""Schrijf voorbeelddata voor het detectiedomein van BobOS v0.2."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "detectie.json"
DETECTIE_URL = "https://mailbvandongen-eng.github.io/detect/"


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_items() -> list[dict[str, str]]:
    """Geef drie simpele voorbeeldregels terug voor detectie."""
    return [
        {"label": "Weer", "value": "Droog tot 14:00"},
        {"label": "Bodem", "value": "Vochtig, goed zoeken"},
        {"label": "Conclusie", "value": "Prima ochtend"},
    ]


def build_payload() -> dict[str, object]:
    """Maak een geldige JSON-structuur voor de detectietegel."""
    return {
        "updated_at": utc_now_iso(),
        "status": "Maandagcondities",
        "items": build_items(),
        "url": DETECTIE_URL,
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
    print(f"[DONE] Detectiedata opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
