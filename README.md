# BobOS v0.3

BobOS is een persoonlijk, mobiel dashboard met losse advies-agents voor nieuws, sport, detectie en vissen. De homepage blijft bewust compact; de agentpagina's geven de diepere analyse en linken daarna door naar de bestaande apps.

## Live URL

[https://mailbvandongen-eng.github.io/bobos](https://mailbvandongen-eng.github.io/bobos)

## Uitgangspunten

- mobile first
- geschikt voor GitHub Pages
- geen backend
- geen database
- geen login
- geen AI-kosten of betaalde API's
- externe links openen in een nieuw tabblad
- volledige artikelen worden niet in BobOS getoond
- licht/donker-thema blijft beschikbaar
- het versienummer staat altijd onderaan in de app

## Architectuur

BobOS leest alleen JSON-bestanden uit `data/`.

De huidige flow is:

`Homepage -> Agentpagina -> Oorspronkelijke app`

De homepage toont nu alleen:

- header
- horizontale agentnavigatie
- compact nieuwsblok
- versienummer

Sport, Detectie en Vissen openen hun eigen agentpagina met uitgebreidere uitleg. Steentijd blijft een directe link naar de externe tool.

## Bestandsstructuur

```text
index.html
news.html
sport.html
detectie.html
vissen.html
meer.html
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
|- json_store.py
|- news_sources.json
|- sport_sources.json
|- detectie_rules.json
\- vissen_rules.json
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

`news.json` bevat nieuwsitems.

`sport.json`, `detectie.json` en `vissen.json` bevatten compacte tegeldata voor de app en uitgebreidere data voor de agentpagina's.

## Agents

De agents zijn lokaal uitvoerbaar:

```powershell
python agents/news_agent.py
python agents/sport_agent.py
python agents/detectie_agent.py
python agents/vissen_agent.py
```

Elke agent schrijft altijd geldige JSON. Als een externe bron tijdelijk faalt, blijft de laatste bruikbare JSON-snapshot staan zodat BobOS niet terugvalt naar lege of kapotte schermen.

### NewsAgent

- gebruikt Nederlandstalige RSS-feeds uit `agents/news_sources.json`
- filtert anderstalige berichten zo veel mogelijk weg
- schrijft maximaal 50 artikelen naar `data/news.json`
- toont geen volledige artikelen in BobOS

### SportAgent

- gebruikt OpenFootball, ESPN Scoreboard, OpenF1 en PDC
- filtert op vandaag
- rangschikt items inhoudelijk met `score`, `reason` en `must_watch`
- geeft extra prioriteit aan Formule 1, darts, WK/topvoetbal en Manchester United
- zet herhalingen en praatformats lager als die ooit in de feed terechtkomen

### DetectieAgent

- gebruikt Open-Meteo voor neerslag van de afgelopen 7 dagen
- gebruikt Open-Meteo voor de verwachting van komende maandag
- combineert dat met vaste kennisregels uit `agents/detectie_rules.json`
- geeft zoekstrategie op landschapstype in plaats van geheime locaties
- bouwt profielscores op voor `Steentijd`, `Romeins` en `Middeleeuws`
- weegt ook seizoen en akker-toegankelijkheid mee

Toekomstige databronnen voor Detectie:

- BoerenBunder / perceeldata voor geoogste akkers
- boomgaarden / nieuwe aanplant
- AHN / PDOK / stroomruggen

Deze bronnen zijn nu alleen genoteerd en nog niet geïmplementeerd.

### VisAgent

- gebruikt Open-Meteo voor wind, luchtdruk, temperatuur, neerslag en CAPE
- kijkt naar luchtdruktrend over ongeveer 48 uur
- gebruikt vaste regels uit `agents/vissen_rules.json`
- bouwt profielscores op voor `Roofvis`, `Meerval` en `Zee`
- gebruikt seizoen, stabiliteit en visbaarheid als hoofdfactoren
- gebruikt bewust nog geen maanstand voor standaard zoetwatervissen

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

`GitHub -> Actions -> kies workflow -> Run workflow`

## Thema en versie

BobOS start standaard in donker thema.

- de themakeuze wordt lokaal opgeslagen in `localStorage`
- het versienummer wordt centraal beheerd in `script.js`

## Lokaal testen

Een simpele lokale server werkt het prettigst:

```powershell
python -m http.server 8000
```

Open daarna:

[http://127.0.0.1:8000/index.html](http://127.0.0.1:8000/index.html)
