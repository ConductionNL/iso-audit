"""Wat er uit een Anthropic-respons gehaald wordt, en met welke thinking-configuratie.

## Waarom dit een eigen module is

Tot 2026-08-17 stond `resp.content[0].text` op acht plekken in vier modules, en de
`thinking`-parameter werd overal weggelaten. Dat weglaten is niet "uit": het betekent
model-afhankelijk gedrag. Gemeten op 2026-08-17 tegen de echte API, met een classificatie-
achtige vraag:

| aanroep | blokken | stop_reason |
|---|---|---|
| `claude-sonnet-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-sonnet-5` met `thinking={"type": "disabled"}` | `['text']` | `max_tokens` |
| `claude-opus-5` zonder `thinking` | `['thinking']` | `max_tokens` |
| `claude-haiku-4-5` met `thinking={"type": "disabled"}` | `['text']` | — |

Zonder de parameter leverden Sonnet 5 en Opus 5 dus **alleen** een thinking-blok en géén
tekstblok: `content[0].text` gooide een `AttributeError`, die werd afgevangen tot een lege
string, en de run meldde zich klaar met nul bevindingen.

Belangrijk detail voor wie dit naleest: dat gedrag is **invoer-afhankelijk**. Op een triviale
vraag ("antwoord met OK") gaf Sonnet 5 wél direct een tekstblok — adaptive thinking betekent
dat het model zelf beslist. De storing was dus niet deterministisch maar afhankelijk van de
vraag, en juist op de echte auditvragen — die om meerstaps redeneren vragen — trad hij op.
Dat is de vervelendste variant: het werkt in een snelle test en faalt op het echte werk.
"""

from __future__ import annotations

from typing import Any

from anthropic.types import ThinkingConfigDisabledParam

GEEN_THINKING: ThinkingConfigDisabledParam = {"type": "disabled"}
"""Thinking expliciet uit, niet weggelaten.

Bewust uit en niet aan: of het oordeel beter wordt mét thinking is aannemelijk, maar dat is
een aparte beslissing met een eigen prijskaartje die uit een meting hoort te komen — zie
`openspec/changes/classificatie-modelkeuze/`, taak 8.2. Deze constante maakt de modelkeuze
eerst *werkend*.

Geverifieerd op 2026-08-17 dat alle drie de kiesbare modellen deze waarde accepteren, Haiku
4.5 inbegrepen; de fix breekt dus niet het enige model dat het daarvoor wél deed.

Wie dit later aanzet moet twee dingen weten: `max_tokens` begrenst dan thinking én antwoord
samen, en op Opus 5 mag `thinking: disabled` alleen bij effort `high` of lager — de combinatie
met `xhigh`/`max` geeft een 400.
"""


class OnleesbaarAntwoordError(Exception):
    """De aanroep slaagde, maar er zat geen tekstblok in de respons.

    Onderscheiden van "het model vond niets": dat is een geldig leeg oordeel, dit is een
    storing. Ze gaven tot 2026-08-17 dezelfde uitkomst — een lege lijst — waardoor een
    onleesbare respons niet van een leeg oordeel te onderscheiden was. Voor een audittool is
    dat de ernstigste vorm van valse dekking: het rapport is leeg en meldt zich compleet.
    """


def tekst_uit(resp: Any) -> str:
    """Geef het eerste tekstblok uit een respons, gezocht op type en niet op positie.

    `content[0]` is een aanname die de API niet garandeert: er kan een thinking-blok, een
    tool-blok of een toekomstig bloktype vóór staan.

    :raises OnleesbaarAntwoordError: als er geen enkel tekstblok in de respons zit.
    """
    for blok in resp.content or []:
        if getattr(blok, "type", None) == "text":
            tekst: str = blok.text
            return tekst
    soorten = ", ".join(str(getattr(b, "type", "?")) for b in resp.content or [])
    raise OnleesbaarAntwoordError(f"geen tekstblok in de respons (blokken: {soorten or 'geen'})")
