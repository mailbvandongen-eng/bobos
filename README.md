# BobOS 0.1

BobOS 0.1 is een lichte statische GitHub Pages-site die voelt als een persoonlijke startpagina voor dagelijks gebruik op een Android-telefoon.

## Live URL

[https://mailbvandongen-eng.github.io/bobos](https://mailbvandongen-eng.github.io/bobos)

## Wat deze versie doet

- toont een mobile-first dashboard met een persoonlijke kop
- toont direct op de homepage een compacte nieuwskaart
- leest appkaarten uit `data/tiles.json`
- leest nieuwsberichten uit `data/news.json`
- haalt RSS-nieuws op via `agents/news_agent.py`
- gebruikt alleen HTML, CSS en JavaScript

Er is bewust geen backend, geen framework en geen buildstap.

## Bestandsstructuur

```text
index.html
news.html
style.css
script.js
README.md
requirements.txt
agents/
|- news_agent.py
\- news_sources.json
data/
|- news.json
\- tiles.json
```

## Apps beheren

De homepage leest de appkaarten uit `data/tiles.json`.

Per app gebruik je:

- `title`
- `description`
- `icon`
- `url`

Voor Lucide gebruik je bij `icon` de iconnaam, bijvoorbeeld `trophy`, `map`, `fish` of `grid-2x2-plus`.

## Nieuws beheren

`agents/news_agent.py` haalt nieuws op uit RSS-feeds die in `agents/news_sources.json` staan. Daarna schrijft de agent maximaal 50 berichten naar `data/news.json`.

Het dashboard en `news.html` lezen daarna alleen `data/news.json`.

Per bericht gebruikt BobOS:

- `title`
- `summary`
- `source`
- `published`
- `url`

## Automatisch verversen

De workflow `.github/workflows/news.yml` draait dagelijks op GitHub Actions en kan ook handmatig gestart worden.

Die workflow:

- installeert Python en de dependencies
- voert `agents/news_agent.py` uit
- commit `data/news.json` als er nieuws is veranderd

## Overzicht bovenaan

De kop van het dashboard wordt opgebouwd in `script.js`.

Daar kun je later eenvoudig aanpassen:

- de begroeting
- hoeveel nieuwsberichten op de homepage getoond worden
- het aantal wedstrijden van vandaag

## Lokaal testen

Een simpele lokale server werkt het prettigst:

```powershell
python -m http.server 8000
```

Open daarna `http://localhost:8000/`.
