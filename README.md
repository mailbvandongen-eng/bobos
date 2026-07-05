# BobOS v0.2

BobOS is een persoonlijk dashboard en PIP voor dagelijks gebruik. Het is geen backendplatform en geen alles-in-een startscherm met een enkele "Vandaag"-tegel. BobOS verdeelt informatie bewust in losse domeinen, elk met een eigen status, eigen data en eigen doorklik.

## Live URL

[https://mailbvandongen-eng.github.io/bobos](https://mailbvandongen-eng.github.io/bobos)

## Uitgangspunten

- mobile first
- geschikt voor GitHub Pages
- geen backend
- geen database
- geen login
- externe links openen in een nieuw tabblad
- volledige artikelen worden niet in BobOS getoond
- licht/donker-thema blijft beschikbaar
- het versienummer staat altijd onderaan in de app

## Werkwijze

Voor dit project geldt een vaste werkafspraak:

- wijzigingen worden standaard gecommit
- wijzigingen worden daarna ook direct gepusht
- het versienummer blijft zichtbaar onderaan in de app

## Architectuur

Het dashboard leest alleen JSON-bestanden. De homepage haalt configuratie op uit `data/tiles.json` en leest per domein het bijbehorende databestand.

De vier hoofdtegels zijn:

- `Nieuws`
- `Sport`
- `Detectie`
- `Vissen`

Elke tegel heeft:

- een eigen icoon
- een statusregel
- compacte items
- een eigen doorklik

## Bestandsstructuur

```text
index.html
news.html
style.css
script.js
README.md
requirements.txt
.github/
\- workflows/
   |- news.yml
   |- sport.yml
   |- detectie.yml
   \- vissen.yml
agents/
|- news_agent.py
|- sport_agent.py
|- detectie_agent.py
|- vissen_agent.py
\- news_sources.json
assets/
|- bobos-logo-dark.svg
\- bobos-logo-light.svg
data/
|- tiles.json
|- news.json
|- sport.json
|- detectie.json
\- vissen.json
```

## Domeinbestanden

BobOS leest de volgende databestanden:

- `data/news.json`
- `data/sport.json`
- `data/detectie.json`
- `data/vissen.json`
- `data/tiles.json`

`news.json` bevat nieuwsitems.

`sport.json`, `detectie.json` en `vissen.json` bevatten statusregels en compacte domeinitems.

## Agents

De agents zijn lokaal uitvoerbaar:

```powershell
python agents/news_agent.py
python agents/sport_agent.py
python agents/detectie_agent.py
python agents/vissen_agent.py
```

Elke agent schrijft altijd geldige JSON, ook als externe data ontbreekt.

### NewsAgent

- gebruikt Nederlandstalige RSS-feeds
- filtert anderstalige berichten zo veel mogelijk weg
- schrijft maximaal 50 artikelen naar `data/news.json`
- toont geen volledige artikelen in BobOS

### SportAgent

- schrijft `data/sport.json`
- gebruikt nu maximaal 3 voorbeelditems voor de Sport-tegel
- kan lokaal draaien met `python agents/sport_agent.py`
- kan later worden gekoppeld aan echte Sport op TV-data

### DetectieAgent

- schrijft voorbeelddata naar `data/detectie.json`
- focust in v0.2 op maandagcondities
- gebruikt nog geen weer-API of kaartanalyse

### VissenAgent

- schrijft voorbeelddata naar `data/vissen.json`
- focust in v0.2 op wind, luchtdruk en een korte conclusie
- gebruikt nog geen weer-API

## GitHub Actions

De agents draaien automatisch via GitHub Actions en kunnen ook handmatig gestart worden.

Workflows:

- `news.yml`
- `sport.yml`
- `detectie.yml`
- `vissen.yml`

Elke workflow:

- ondersteunt `workflow_dispatch`
- installeert Python
- installeert dependencies uit `requirements.txt`
- voert de juiste agent uit
- commit alleen gewijzigde JSON-data
- pusht terug naar de repository

Handmatig starten kan via:

`GitHub Actions -> Run workflow`

Voor Sport specifiek:

`GitHub Actions -> SportAgent -> Run workflow`

## Thema en versie

BobOS start standaard in donker thema.

- de themakeuze wordt lokaal opgeslagen in `localStorage`
- het dashboard wisselt ook automatisch van logo per thema
- het versienummer wordt centraal beheerd in `script.js`

## Lokaal testen

Een simpele lokale server werkt het prettigst:

```powershell
python -m http.server 8000
```

Open daarna:

[http://127.0.0.1:8000/index.html](http://127.0.0.1:8000/index.html)
