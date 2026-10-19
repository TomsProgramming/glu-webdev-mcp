# GLU Web Development MCP

[![tests](https://github.com/TomsProgramming/glu-webdev-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/TomsProgramming/glu-webdev-mcp/actions/workflows/tests.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Geen dependencies](https://img.shields.io/badge/dependencies-geen-brightgreen)
[![Licentie: MIT](https://img.shields.io/badge/licentie-MIT-lightgrey)](LICENSE)

Een [MCP-server](https://modelcontextprotocol.io) waarmee **Claude** de complete [GLU Web Development Notion-site](https://gluwebdev.notion.site/Web-Development-b8d9ced798b741d3a375fcafbb470a43) kan lezen en doorzoeken. Dat zijn alle opdrachten per leerjaar, elke subpagina, databases, afbeeldingen en de links die erin staan: GitHub-repo's, YouTube-video's en documentatie.

Je vraagt Claude bijvoorbeeld *"Wat zijn de eisen van de Hoveniers Website?"*. Claude zoekt dan zelf de juiste pagina op, volgt de links en geeft antwoord.

> Dit is een onofficieel hulpmiddel van een student. Het leest alleen pagina's die openbaar op internet staan en heeft geen banden met het Grafisch Lyceum Utrecht.

## Wat kan het?

- 📚 **Alle opdrachten per leerjaar**: modules en ontwikkelweken met periode, plus losse pagina's zoals Stage en Loopbaan.
- 📄 **Elke pagina volledig lezen**: tekst, koppen, lijsten, to-do's, code, tabellen, kolommen, tabs, callouts, synced blocks en databases.
- 🔗 **Links volgen, eindeloos diep**: subpagina's, links naar andere Notion-pagina's en links naar externe websites.
- 🖼️ **Afbeeldingen bekijken**: Claude krijgt de afbeelding echt te zien, bijvoorbeeld een wireframe of infographic.
- 🌐 **Externe bronnen**:
  - GitHub-repo's: bestandslijst en README.
  - GitHub-bestanden: de broncode.
  - YouTube: titel en kanaal.
  - Overige websites: de hoofdtekst, zonder menu's en reclame.
- 🔎 **Zoeken in alles**: full-text zoeken in ruim 1000 pagina's, met per treffer de opdracht waar hij bij hoort.
- 🪙 **Zuinig met tokens**: compacte markdown, korte verwijzingen en lange pagina's in delen. Zie [Tokens besparen](#tokens-besparen).
- ⚡ **Snel en zonder installatie**: alleen Python nodig, geen `pip install`. Pagina's worden gecachet en de zoekindex wordt op de achtergrond bijgewerkt.

## Installatie

### 1. Wat je nodig hebt

- **Python 3.10 of nieuwer**. Check het met `python --version`. Installeer je Python op Windows via [python.org](https://www.python.org/downloads/)? Vink dan *"Add python.exe to PATH"* aan.
- **Claude Code** of **Claude Desktop**.

### 2. Downloaden

```bash
git clone https://github.com/TomsProgramming/glu-webdev-mcp.git
```

Geen git? Download dan de ZIP via de groene knop **Code → Download ZIP** en pak hem uit.

### 3. Toevoegen aan Claude

Gebruik in de voorbeelden het pad naar jouw map. In de voorbeelden staat de repo in `C:\Users\jij\glu-webdev-mcp`.

#### Claude Code (CLI, VS Code of de Code-tab in de Claude-app)

```bash
claude mcp add glu-webdev --scope user -- python "C:\Users\jij\glu-webdev-mcp\server.py"
```

Op macOS/Linux gebruik je `python3` en een pad zoals `~/glu-webdev-mcp/server.py`. Met `--scope user` werkt hij in al je projecten. Start daarna een nieuwe sessie.

#### Claude Desktop

1. Open **Settings → Developer → Edit Config**. Dat opent `claude_desktop_config.json`.
2. Voeg de server toe. Staat er al een `mcpServers`-blok? Voeg dan alleen `glu-webdev` toe.

```json
{
  "mcpServers": {
    "glu-webdev": {
      "command": "python",
      "args": ["C:\\Users\\jij\\glu-webdev-mcp\\server.py"]
    }
  }
}
```

3. Sluit Claude Desktop **helemaal** af (ook in het systeemvak) en start hem opnieuw.

> **Tip (Windows):** krijg je de melding dat de server niet kan starten? Vul dan bij `command` het volledige pad naar Python in. Dat pad krijg je met `where python`, bijvoorbeeld `C:\\Users\\jij\\AppData\\Local\\Programs\\Python\\Python313\\python.exe`.

#### Alternatief: installeren als pakket

Wil je niet clonen? Met [pipx](https://pipx.pypa.io) of [uv](https://docs.astral.sh/uv/) kan het ook:

```bash
pipx install git+https://github.com/TomsProgramming/glu-webdev-mcp.git
```

```bash
claude mcp add glu-webdev --scope user -- glu-webdev-mcp
```

Met uv kun je in Claude Desktop ook `"command": "uvx"` gebruiken, met `"args": ["--from", "git+https://github.com/TomsProgramming/glu-webdev-mcp.git", "glu-webdev-mcp"]`.

### 4. Controleren

- **Claude Code**: `claude mcp list` moet `glu-webdev` tonen met `✓ Connected`. In een sessie kan het ook met `/mcp`.
- **Claude Desktop**: onder het 🔧-icoon in het chatvenster staat `glu-webdev` met drie tools.

Bij de eerste start haalt de server op de achtergrond alle ±1000 pagina's op. Dat duurt ongeveer 6 minuten, omdat Notion snelle requests blokkeert. Lezen werkt meteen, zoeken is na die eerste keer compleet. Je kunt dit ook vooraf doen:

```bash
python server.py warm
```

## Gebruik

Stel gewoon je vraag; Claude kiest zelf de tools. Een paar voorbeelden:

- *"Welke opdrachten zijn er in leerjaar 2?"*
- *"Wat moet ik doen voor 4.2 Hoveniers Website en hoe word ik beoordeeld?"*
- *"Lees de CBR Challenge en bekijk de GitHub-repo met de aangeleverde data."*
- *"Waar wordt uitgelegd hoe migrations in Laravel werken?"*
- *"Maak een planning voor 9.2 Berlins Best! op basis van de opdracht."*
- *"Wat staat er op de afbeelding bij de Berlins Best-opdracht?"*

## Tools

| Tool | Wat het doet |
|------|--------------|
| `list_assignments(leerjaar?)` | Alle opdrachten per leerjaar (`4.2 module: Hoveniers Website @920ee7f3`) plus overige pagina's. |
| `read(target, section?, part?)` | Leest een Notion-pagina, afbeelding of webpagina als compacte markdown. |
| `search(query, limit?)` | Zoekt in de tekst van alle pagina's en geeft per treffer de opdracht en een fragment. |

`target` van `read` mag het volgende zijn:

- een **@ref** uit eerdere output, bijvoorbeeld `@920ee7f3`;
- een **opdrachtnaam of periode**, bijvoorbeeld `hoveniers` of `4.1 module`;
- een **Notion-URL of -id**;
- een gewone **URL**, bijvoorbeeld `https://laravel.com/docs/migrations`.

Links in de output zien eruit als `[Titel](@ref)` en afbeeldingen als `[img: naam](@ref)`. Claude volgt ze door die `@ref` te lezen, en zo kan hij steeds dieper. Gewone web-links op Notion-pagina's blijven volledige URL's, zodat Claude ze ook aan jou kan geven.

Een lange pagina komt in delen. Het eerste deel bevat een overzicht van de koppen. Claude kan dan `part=2` lezen, of met `section="beoordeling"` alleen het stuk dat hij nodig heeft.

## Tokens besparen

Elke token in een tool-antwoord kost context, en dus geld of gebruikslimiet. Daarom:

| Maatregel | Effect |
|-----------|--------|
| Drie compacte tools, korte beschrijvingen | ±350 tokens per gesprek voor de tooldefinities |
| `@ref` in plaats van Notion-id (`@920ee7f3` i.p.v. `eb7edf06-b00d-43e6-beed-882e920ee7f3`) | ±20 tokens minder **per link** |
| Markdown zonder opmaak die niets toevoegt (kleuren, lege regels, scheidingslijnen, ID's) | gemiddelde pagina ±800 tokens |
| Externe sites: alleen de hoofdinhoud, menu's eruit, links als ref | W3Schools-pagina: 90.000 → 3.500 tekens |
| Lange pagina's in delen, of één sectie | Claude leest alleen wat nodig is |
| Afbeeldingen verkleind tot 1000 px breed | genoeg om te lezen, niet onnodig groot |

## Instellingen

Alle instellingen zijn optioneel en gaan via omgevingsvariabelen.

| Variabele | Standaard | Betekenis |
|-----------|-----------|-----------|
| `GLU_CACHE_HOURS` | `12` | Hoe lang pagina's in de cache geldig blijven. |
| `GLU_MAX_CHARS` | `12000` | Maximale lengte van één antwoord; langere pagina's worden opgedeeld. |
| `GLU_WORKERS` | `3` | Gelijktijdige requests naar Notion. Hoger is sneller, maar dan krijg je eerder een rate limit. |
| `GLU_CACHE_DIR` | zie hieronder | Map voor de cache. |
| `GLU_SITE`, `GLU_ROOT_PAGE`, `GLU_SPACE_ID` | GLU Web Development | Andere openbare Notion-site gebruiken. |

De cache staat standaard in `%LOCALAPPDATA%\glu-webdev-mcp` (Windows), `~/Library/Caches/glu-webdev-mcp` (macOS) of `~/.cache/glu-webdev-mcp` (Linux).

Een instelling meegeven:

```bash
claude mcp add glu-webdev --scope user -e GLU_CACHE_HOURS=24 -- python "C:\Users\jij\glu-webdev-mcp\server.py"
```

In Claude Desktop gebruik je `"env": { "GLU_CACHE_HOURS": "24" }` naast `command` en `args`.

## Zelf testen zonder Claude

```bash
python server.py list 2
```

```bash
python server.py read "hoveniers"
```

```bash
python server.py search "laravel migration"
```

```bash
python server.py warm
```

## Problemen oplossen

| Probleem | Oplossing |
|----------|-----------|
| Server start niet / `python` niet gevonden | Gebruik het volledige pad naar `python.exe` (zie de tip bij Claude Desktop). |
| Inhoud is verouderd | Verwijder de cachemap, of verlaag `GLU_CACHE_HOURS`. |
| Zoeken geeft "index nog bezig" | De eerste crawl loopt nog. Wacht een paar minuten, of draai `python server.py warm`. |
| Fouten in Claude Desktop | Bekijk de logs via Settings → Developer, of `%APPDATA%\Claude\logs\mcp-server-glu-webdev.log`. |
| "pagina niet gevonden of niet openbaar" | Die pagina staat niet openbaar op Notion. Dat kan de server niet omzeilen. |

## Hoe werkt het?

Kort samengevat:

1. De server gebruikt dezelfde (niet-officiële) API als de Notion-website zelf, om openbare pagina's op te halen.
2. Hij zet de Notion-blokken om naar compacte markdown en vervangt lange id's door korte `@ref`s.
3. Elke pagina wordt gecachet. Een crawler bouwt op de achtergrond een zoekindex over alle pagina's.

Het volledige verhaal staat in **[docs/hoe-het-werkt.md](docs/hoe-het-werkt.md)**: architectuur, gebruikte endpoints, caching, rate limiting en de keuzes daarachter.

## Ontwikkelen

```
glu_webdev_mcp/
├── server.py    MCP-protocol (JSON-RPC via stdio) en CLI
├── tools.py     de drie tools en hun definities
├── notion.py    pagina's ophalen via de Notion-API
├── render.py    Notion-blokken → markdown, opdrachtenlijst
├── store.py     cache van gerenderde pagina's
├── search.py    crawler en zoekindex
├── web.py       externe websites, GitHub, YouTube, afbeeldingen
├── paging.py    lange pagina's opdelen, secties
├── refs.py      korte @refs
├── net.py       HTTP met throttling en retries
├── config.py    instellingen
└── util.py      hulpfuncties
server.py        starter, zodat het zonder installatie werkt
tests/           offline tests (geen netwerk nodig)
```

De tests draaien zonder netwerk en zonder dependencies:

```bash
python -m unittest discover -s tests -t . -v
```

Verandert de markdown-output? Verhoog dan `RENDER_VERSION` in `config.py`. Bestaande caches worden dan automatisch vernieuwd.

## Licentie

[MIT](LICENSE) © Tom Tiedemann. De inhoud van de Notion-site is van het Grafisch Lyceum Utrecht en de docenten die hem schrijven.
