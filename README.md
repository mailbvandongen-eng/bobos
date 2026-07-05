# BobOS 0.1

BobOS is een persoonlijk dashboard voor dagelijks gebruik op mobiel. Het is bedoeld als snelle startpagina: compact, scanbaar en gericht op nieuws en vaste apps.

## Live URL

[https://mailbvandongen-eng.github.io/bobos](https://mailbvandongen-eng.github.io/bobos)

## Wat deze versie doet

- toont een mobile-first dashboard met compacte nieuwsregels
- leest appkaarten uit `data/tiles.json`
- leest nieuwsberichten uit `data/news.json`
- haalt RSS-nieuws op via `agents/news_agent.py`
- gebruikt standaard Nederlandstalige RSS-feeds
- filtert anderstalige berichten zo veel mogelijk weg
- bewaart de licht/donker-keuze lokaal in `localStorage`
- gebruikt alleen HTML, CSS en JavaScript

Er is bewust geen backend, geen framework en geen buildstap.

## Werkwijze

Voor dit project geldt een vaste werkafspraak:

- wijzigingen worden standaard gecommit
- wijzigingen worden daarna ook direct gepusht

## Bestandsstructuur

```text
index.html
news.html
style.css
script.js
README.md
requirements.txt
assets/
|- bobos-logo-dark.svg
|- bobos-logo-light.svg
agents/
|- news_agent.py
\- news_sources.json
data/
|- news.json
\- tiles.json
```

## Apps beheren

De homepage leest de appkaarten uit `data/tiles.json`.

Apps openen bewust in dezelfde tab, zodat BobOS als startpagina blijft aanvoelen en niet als stapel losse browservensters.

Per app gebruik je:

- `title`
- `description`
- `icon`
- `url`

Voor Lucide gebruik je bij `icon` de iconnaam, bijvoorbeeld `trophy`, `map`, `fish` of `grid-2x2-plus`.

## Nieuws beheren

`agents/news_agent.py` haalt nieuws op uit RSS-feeds die in `agents/news_sources.json` staan. De standaardlijst bevat alleen Nederlandstalige bronnen die technisch zijn gecontroleerd. Die bronlijst gebruikt per feed:

- `category`
- `name`
- `rss`

Daarna schrijft de agent maximaal 50 berichten naar `data/news.json`.

Het dashboard en `news.html` lezen daarna alleen `data/news.json`. Nieuwsitems openen altijd de originele bron in een nieuwe tab.

De agent gebruikt een lichte taalfilter:

- feeds met taalcode `nl` mogen door
- twijfelgevallen moeten genoeg Nederlandse stopwoorden bevatten
- anderstalige berichten worden overgeslagen

Per bericht gebruikt BobOS:

- `title`
- `summary`
- `source`
- `published`
- `category`
- `image`
- `url`

BobOS toont bewust alleen compacte nieuwsregels en geen volledige artikelteksten.

De homepage toont alleen titel, bron en datum. De nieuwspagina blijft ook compact en toont hooguit een korte afgekorte samenvatting.

## Thema

BobOS start standaard in donker thema.

- de schakelaar staat rechtsboven
- de keuze wordt lokaal opgeslagen in `localStorage`
- de keuze geldt voor dashboard en nieuwspagina

## Automatisch verversen

De workflow `.github/workflows/news.yml` draait dagelijks op GitHub Actions en kan ook handmatig gestart worden.

Die workflow:

- installeert Python en de dependencies
- voert `agents/news_agent.py` uit
- commit `data/news.json` als er nieuws is veranderd

## Overzicht bovenaan

De kop van het dashboard wordt opgebouwd in `script.js`.

Daar kun je later eenvoudig aanpassen:

- de tijdsafhankelijke begroeting
- hoeveel nieuwsberichten op de homepage getoond worden

## Later slimmer vullen

De huidige NewsAgent haalt feeds direct op en schrijft ze naar `data/news.json`. Later kan die agent slimmer worden in selectie, filtering en prioritering.

## Lokaal testen

Een simpele lokale server werkt het prettigst:

```powershell
python -m http.server 8000
```

Open daarna `http://localhost:8000/`.

## Nog te controleren bronnen

Deze bronnen zijn bewust nog niet als standaardfeed opgenomen, omdat de RSS-feed ontbrak, onzeker was of eerst nog gecontroleerd moet worden:

- Rijksmuseum van Oudheden (RMO)
- NEMO Kennislink
- Sportvisserij Nederland
- Visdeal blog
- RCE Service
- ADC Archeoprojecten
- Dartsnieuws.com
- Roofmeister YouTube RSS
- betrouwbare Nederlandstalige feeds voor metaaldetectie en drones/S30 Pro
