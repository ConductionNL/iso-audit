"""Eén bevinding per afwijking, niet per raakvlak.

De classificatie oordeelt per (document, clausule). Dat is de juiste eenheid om te *meten* — de
koppeling weet welke clausules een document raakt, en per clausule valt een oordeel te geven dat
op de norm terug te voeren is. Het is niet de juiste eenheid om te *tellen*.

Gemeten op de run van 2026-08-31: 186 NC's over 68 documenten. Eén memo — "Memo NC-2025
Onvolledige evaluatie Q3/Q4", waarin de organisatie één afwijking vastlegt en afhandelt —
leverde er tien op, verspreid over §5.3, §7.4, §7.5, §7.5.2, §9.2, A.5.35 en de 9001-tegenhangers
daarvan. Eén afwijking, tien raakvlakken, tien NC's. Een externe auditor telde er nul.

Het verschil zit niet in het oordeel maar in de eenheid. Een auditor schrijft één afwijking op en
noemt daaronder de clausules die hij raakt. Dat is wat hier gebeurt:

- **Groeperen op (document, klasse, thema).** Eén document dat twee ongerelateerde problemen
  heeft, houdt twee afwijkingen — het thema is wat ze uit elkaar houdt. Groeperen op document
  alleen zou die twee onterecht samentrekken.
- **De overige clausules blijven zichtbaar** als `extra_clauses`; de memo citeert ze allemaal.
  Er verdwijnt dus geen raakvlak, het telt alleen niet meer als aparte afwijking.
- **`gebundeld_uit` houdt de link naar elke onderliggende bevindingsrij.** De DB behoudt elke
  (document, clausule)-beoordeling als bewijs; deze lijst is de weg terug.

Dubbeltelling over normen valt hier vanzelf weg. Drieëntwintig Annex SL-nummers bestaan in beide
normen, en `bouw_bevindingen` maakt er twee rijen van uit één modeloordeel. Dat is een kopie, geen
tweede beoordeling: §7.5 heet in beide normen "Gedocumenteerde informatie" en §5.3 gaat in beide
over rollen en bevoegdheden — het verschil is de scope (ISMS of KMS), niet het onderwerp. In de
bundel staat de clausule één keer, met beide normen erbij genoemd.
"""

from __future__ import annotations

from collections import defaultdict

from iso_audit.memo.models import BronRef, Finding

GEEN_THEMA = "Overig"
"""Zonder thema is er niets om op te bundelen; die bevindingen blijven los.

Twee bevindingen samentrekken omdat ze allebei geen label hebben, zou een verband suggereren dat
er niet is — dezelfde afweging als in `memo/groepering.py`."""


def bundel(findings: list[Finding]) -> list[Finding]:
    """Bundel per (document, klasse, thema) tot één bevinding per afwijking.

    Volgorde blijft die van de invoer: de eerste bevinding van een groep is de drager, en de
    lijst komt in de volgorde waarin die dragers binnenkwamen. Een run die op clausulenummer
    sorteert, houdt dus een op clausulenummer gesorteerde uitkomst.
    """
    groepen: dict[tuple[str, str, str], list[Finding]] = defaultdict(list)
    volgorde: list[tuple[str, str, str]] = []
    los: list[Finding] = []
    for f in findings:
        doc = _doc_id(f)
        thema = (f.thema or "").strip()
        if not doc or not thema or thema == GEEN_THEMA:
            los.append(f)
            continue
        sleutel = (doc, f.severity, thema)
        if sleutel not in groepen:
            volgorde.append(sleutel)
        groepen[sleutel].append(f)

    uit = [_samenvoegen(groepen[s]) for s in volgorde]
    return _op_invoervolgorde(findings, uit + los)


def _doc_id(f: Finding) -> str:
    """Het brondocument van een bevinding; leeg als er geen bron aan hangt."""
    return f.bronnen[0].doc_id if f.bronnen else ""


def _op_invoervolgorde(origineel: list[Finding], uit: list[Finding]) -> list[Finding]:
    """Herstel de volgorde van de invoer op basis van de eerste bevinding per bundel."""
    positie = {f.id: i for i, f in enumerate(origineel)}
    return sorted(uit, key=lambda f: positie.get(f.id, len(positie)))


def _samenvoegen(leden: list[Finding]) -> Finding:
    """Eén bevinding uit een groep; de eerste is de drager en houdt zijn id.

    Het id van de drager blijft staan zodat een triage-beslissing en de trail-regels die eraan
    hangen niet losraken van hun bevinding. De overige ids staan in `gebundeld_uit`.
    """
    drager = leden[0]
    if len(leden) == 1:
        return drager

    clausules = _clausules_met_normen(leden)
    hoofd = clausules[0][0]
    rest = [c for c, _ in clausules[1:]]
    beschrijvingen = list(dict.fromkeys(f.description.strip() for f in leden if f.description))

    return drager.model_copy(
        update={
            "clause": hoofd,
            "extra_clauses": rest,
            "title": _titel(leden, clausules),
            "description": _beschrijving(beschrijvingen),
            "bronnen": _bronnen(leden),
            "gebundeld_uit": [f.id for f in leden],
            "normen": sorted({n for _, normen in clausules for n in normen}),
        }
    )


def _clausules_met_normen(leden: list[Finding]) -> list[tuple[str, list[str]]]:
    """Elke geraakte clausule één keer, met de normen waaronder hij is beoordeeld.

    Op clausulenummer gesorteerd, zodat de volgorde niet afhangt van de volgorde waarin de
    documenten toevallig zijn geclassificeerd.
    """
    per_clausule: dict[str, set[str]] = defaultdict(set)
    for f in leden:
        for c in [f.clause, *f.extra_clauses]:
            per_clausule[c].add(f.standard)
    return [(c, sorted(per_clausule[c])) for c in sorted(per_clausule, key=_sorteersleutel)]


def _sorteersleutel(clausule: str) -> tuple[int, tuple[object, ...]]:
    """Sorteer §4.1 vóór §10.2 en zet Bijlage A achter de managementclausules.

    Zonder dit sorteert "10.2" vóór "4.1" en staat A.5.1 tussen de hoofdstukken. De prefix telt
    als eerste sleutel; daarbinnen wordt op nummerdelen gesorteerd."""
    kaal = clausule[2:] if clausule.startswith("A.") else clausule
    delen: list[object] = []
    for stuk in kaal.split("."):
        delen.append(int(stuk) if stuk.isdigit() else stuk)
    return (1 if clausule.startswith("A.") else 0, tuple(delen))


def _titel(leden: list[Finding], clausules: list[tuple[str, list[str]]]) -> str:
    """ "§5.3, §7.4, §7.5 — <thema> [document]" — de raakvlakken staan in de titel.

    Bij meer dan vier clausules wordt het er niet leesbaarder op; dan noemt de titel het aantal.
    De volledige lijst staat in `extra_clauses` en komt in de memo als citaat terug, dus er
    verdwijnt niets — alleen de titel blijft leesbaar.
    """
    nummers = [f"§{c}" for c, _ in clausules]
    kop = (
        ", ".join(nummers) if len(nummers) <= 4 else f"{', '.join(nummers[:4])} +{len(nummers) - 4}"
    )
    doc = leden[0].bronnen[0].doc_naam if leden[0].bronnen else ""
    thema = leden[0].thema or ""
    return f"{kop} — {thema}" + (f" [{doc[:50]}]" if doc else "")


def _beschrijving(beschrijvingen: list[str]) -> str:
    """De beschrijvingen onder elkaar, ontdubbeld.

    Niet één representant: van tien raakvlakken één beschrijving overhouden maakt van een
    afwijking met tien kanten een anekdote met één. De auditor moet kunnen zien wat er per
    clausule is geconstateerd voordat hij hem als één afwijking afdoet.
    """
    if len(beschrijvingen) == 1:
        return beschrijvingen[0]
    return "\n".join(f"- {b}" for b in beschrijvingen)


def _bronnen(leden: list[Finding]) -> list[BronRef]:
    """De bronverwijzingen, ontdubbeld op (herkomst, doc_id)."""
    per: dict[tuple[str, str], BronRef] = {}
    for f in leden:
        for b in f.bronnen:
            per.setdefault((b.herkomst, b.doc_id), b)
    return list(per.values())
