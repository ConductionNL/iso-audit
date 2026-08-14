"""Read-only tools waarmee een agent de bestaande bron-adapters gebruikt.

## Waarom dit dun is

Elke tool is een dunne laag om een bestaande `Source`-methode. Er komt geen tweede
manier om een bron te lezen bij: `sources.get(naam)` blijft de enige ingang, en het
Source-protocol wijzigt niet. Een agent kan daardoor niets wat de vaste pipeline niet ook
kan — hij kan alleen zelf bepalen in welke volgorde en hoe diep.

## Waarom geen enkele tool schrijft

`stel_bevinding_voor` schrijft **niets**. Hij zet een kandidaat in de run-context; de
deterministische join (`api/runs.py:dedup_sleutel` + `voeg_toe`) bepaalt daarna wat één
bevinding is. Een auditor moet kunnen uitleggen waarom twee bevindingen zijn samengevoegd,
en "een model vond ze hetzelfde" is geen uitleg.

Dat is ook waarom er geen tool bestaat die `findings.json`, `runs.jsonl` of de database
aanraakt. `tests/agent/test_geen_schrijvende_tools.py` faalt zodra dat verandert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from anthropic import beta_tool

MAX_DOCUMENTEN = 50
"""Plafond per bron-uitvraag. Zonder plafond kan één `lijst_documenten` de hele
context vullen en is er geen ruimte meer om te redeneren."""

MAX_INHOUD = 8000
"""Tekens per document. Een agent die de volledige tekst van tien documenten inleest,
kost meer dan hij oplevert; hij kan gericht doorvragen."""


@dataclass(slots=True)
class RunContext:
    """Wat de tools tijdens één run bijhouden.

    Dit is bewust géén globale state: elke run krijgt zijn eigen context, zodat twee
    gelijktijdige runs elkaars kandidaten niet zien.
    """

    audit_id: str
    kandidaten: list[dict[str, Any]] = field(default_factory=list)
    aanroepen: list[dict[str, Any]] = field(default_factory=list)

    def leg_vast(self, tool: str, **velden: str | int) -> None:
        """Registreer een tool-aanroep voor de trail.

        Alleen wát er is opgevraagd, nooit de opgehaalde inhoud: de trail moet
        herleidbaar zijn, niet een tweede kopie van het bewijs.
        """
        self.aanroepen.append({"tool": tool, **velden})


_context: RunContext | None = None


def zet_context(ctx: RunContext | None) -> None:
    """Koppel de run-context. De tools zijn module-functies omdat de SDK-decorator dat
    vraagt; deze setter houdt de state expliciet in plaats van impliciet."""
    global _context
    _context = ctx


def _ctx() -> RunContext:
    if _context is None:
        raise RuntimeError("Geen run-context actief; roep zet_context() aan.")
    return _context


def _adapter(bron: str) -> Any:
    from iso_audit import sources as registry

    return registry.get(bron)()


@beta_tool
def lijst_bronnen() -> str:
    """Geef de beschikbare bronnen en of ze gekoppeld zijn.

    Gebruik dit eerst: een bron die niet gekoppeld is, kun je niet lezen, en dat is een
    bevinding voor de auditor — geen fout om omheen te werken.
    """
    from iso_audit.api.session import bron_health

    _ctx().leg_vast("lijst_bronnen")
    health = bron_health()
    return json.dumps(
        [{"bron": n, "gekoppeld": bool(h.get("connected"))} for n, h in health.items()],
        ensure_ascii=False,
    )


@beta_tool
def lijst_documenten(bron: str) -> str:
    """Geef de documenten van één bron: id, titel en type.

    Args:
        bron: Naam van de bron, zoals `lijst_bronnen` die teruggaf.
    """
    ctx = _ctx()
    docs = []
    for i, doc in enumerate(_adapter(bron).list_documents()):
        if i >= MAX_DOCUMENTEN:
            break
        docs.append(
            {
                "id": getattr(doc, "id", None) or getattr(doc, "doc_id", ""),
                "titel": getattr(doc, "titel", None) or getattr(doc, "title", ""),
            }
        )
    ctx.leg_vast("lijst_documenten", bron=bron, aantal=len(docs))
    return json.dumps({"bron": bron, "documenten": docs}, ensure_ascii=False)


@beta_tool
def lees_document(bron: str, doc_id: str) -> str:
    """Lees de inhoud van één document, afgekapt op een vaste lengte.

    Args:
        bron: Naam van de bron.
        doc_id: Het id uit `lijst_documenten`.
    """
    ctx = _ctx()
    adapter = _adapter(bron)
    doc = next(
        (
            d
            for d in adapter.list_documents()
            if str(getattr(d, "id", getattr(d, "doc_id", ""))) == doc_id
        ),
        None,
    )
    if doc is None:
        ctx.leg_vast("lees_document", bron=bron, doc_id=doc_id, gevonden=0)
        return json.dumps({"fout": "Document niet gevonden in deze bron."}, ensure_ascii=False)

    inhoud = adapter.fetch_content(doc) or ""
    afgekapt = len(inhoud) > MAX_INHOUD
    ctx.leg_vast("lees_document", bron=bron, doc_id=doc_id, tekens=len(inhoud))
    return json.dumps(
        {"doc_id": doc_id, "inhoud": inhoud[:MAX_INHOUD], "afgekapt": afgekapt},
        ensure_ascii=False,
    )


@beta_tool
def stel_bevinding_voor(
    standard: str, clause: str, titel: str, onderbouwing: str, bron: str, bewijs_id: str
) -> str:
    """Stel één bevinding voor. Dit schrijft niets — het is een voorstel.

    Elke bevinding MOET naar bewijs verwijzen. Kun je geen document- of ticket-id noemen,
    dan is het geen bevinding maar een vraag; meld dat dan als zodanig in je antwoord.

    Args:
        standard: De norm, bv. `iso-9001-2015`.
        clause: De clausule, bv. `10.2`.
        titel: Korte omschrijving.
        onderbouwing: Waarom dit een bevinding is, met verwijzing naar het bewijs.
        bron: Waar het bewijs vandaan komt.
        bewijs_id: Document- of ticket-id.
    """
    ctx = _ctx()
    if not bewijs_id.strip():
        return "Geweigerd: een bevinding zonder bewijs-id is een vraag, geen bevinding."

    ctx.kandidaten.append(
        {
            "standard": standard,
            "clause": clause,
            "title": titel,
            "description": onderbouwing,
            "source": bron,
            "bewijs_id": bewijs_id,
        }
    )
    ctx.leg_vast("stel_bevinding_voor", bron=bron, clause=clause, bewijs_id=bewijs_id)
    return f"Voorstel opgenomen ({len(ctx.kandidaten)} tot nu toe). Niet opgeslagen."


ALLE_TOOLS = (lijst_bronnen, lijst_documenten, lees_document, stel_bevinding_voor)
"""Precies de tools die een agent krijgt. Read-only, plus één voorstel-kanaal."""
