"""Schrijf compact maandagadvies voor DetectieAgent v0.2."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "data" / "detectie.json"
DETECTIE_URL = "https://mailbvandongen-eng.github.io/detect/"
DEFAULT_WEEK_STATE = "natte_week"


@dataclass(frozen=True)
class DetectieAdvice:
    """Compact terreinadvies voor de Detectie-tegel."""

    status: str
    score: int
    best_choice: str
    avoid_choice: str
    tip: str
    details: list[str]


def utc_now_iso() -> str:
    """Geef een compacte UTC-tijd terug voor JSON-opslag."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_advice(week_state: str = DEFAULT_WEEK_STATE) -> DetectieAdvice:
    """Maak een compacte detectiebeoordeling op basis van vaste voorbeeldregels."""
    normalized_state = str(week_state).strip().lower()

    if normalized_state == "zeer_nat":
        return DetectieAdvice(
            status="Maandagadvies",
            score=2,
            best_choice="Hoge zandgronden",
            avoid_choice="Komklei / lage weilanden",
            tip="Zoek hoger en droger",
            details=[
                "Veel regen maakt lage weilanden, komklei en natte kleigronden minder aantrekkelijk.",
                "Kies liever voor hogere zandgronden, dekzandruggen en andere droge ruggen.",
                "Voor steentijdzoeken blijft hoger zand bruikbaar, maar mik vooral op plekken die nog begaanbaar zijn.",
            ],
        )

    if normalized_state == "droge_week":
        return DetectieAdvice(
            status="Maandagadvies",
            score=3,
            best_choice="Klei en akkers",
            avoid_choice="Keiharde droge grond",
            tip="Let op stoppels / begaanbaarheid",
            details=[
                "Een droge week maakt sommige kleiakkers en open akkers beter bereikbaar voor een zoekdag.",
                "Keiharde droge grond blijft minder prettig voor signalen, prikken en graven.",
                "Kies vooral begaanbare akkers en let op stoppels, hardheid van de toplaag en werkbare stukken.",
            ],
        )

    return DetectieAdvice(
        status="Maandagadvies",
        score=4,
        best_choice="Hoger zand / stroomrug",
        avoid_choice="Lage natte klei",
        tip="Steentijd op nat zand",
        details=[
            "Regen in de afgelopen week maakt lage kleigronden minder aantrekkelijk.",
            "Hoger gelegen zandgronden, rivierduinen, dekzandruggen en stroomruggen blijven interessant.",
            "Betuwe niet uitsluiten: hoge stroomruggen en oude oeverwallen kunnen juist goed zijn.",
        ],
    )


def build_payload(advice: DetectieAdvice) -> dict[str, object]:
    """Maak de JSON-structuur voor de compacte Detectie-tegel."""
    return {
        "updated_at": utc_now_iso(),
        "status": advice.status,
        "score": advice.score,
        "items": [
            {
                "label": "Beste keuze",
                "value": advice.best_choice,
            },
            {
                "label": "Vermijd",
                "value": advice.avoid_choice,
            },
            {
                "label": "Tip",
                "value": advice.tip,
            },
        ],
        "details": advice.details,
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
    payload = build_payload(build_advice())
    save_payload(payload)
    print(f"[DONE] Detectiedata opgeslagen in {OUTPUT_PATH}.")


if __name__ == "__main__":
    main()
