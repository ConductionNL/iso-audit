"""Bronnen ophalen voor de Bronbevrager — clausule eerst, dan tekst.

## Waarom clausule eerst

Bevat de vraag een clausule (`8.24`, "clausule 5.27"), dan is `clause_matches` de ingang:
dat is een exacte koppeling die de pipeline zelf heeft gelegd. Zoeken op "encryptie" vindt
documenten die het woord bevatten; zoeken op 8.24 vindt de documenten die het tool aan die
eis heeft gekoppeld — inclusief die waar het woord niet in staat. Alleen zonder clausule
valt het ophalen terug op `documents_fts`.

## Geen nieuwe index

Alle vier de bronnen zijn al doorzoekbaar: `documents_fts` (FTS5 met triggers),
`clause_matches`, `data/normteksten.lookup()`, en `bevindingen` + `decisions`. Semantisch
zoeken met embeddings is overwogen en verworpen: het vindt dingen die FTS5 mist, maar het is
een tweede administratie die uiteenloopt met de eerste zodra iemand vergeet hem bij te
werken. Blijkt trefwoordzoeken te grofmazig, dan is dat een meting en een volgende change.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from iso_audit.data import normteksten
from iso_audit.sources.opvolgpunten import HERKOMST_ACHTERVOEGSEL

MAX_DOCUMENTEN = 12
"""Bovengrens op het aantal documenten dat aan het model meegaat.

Niet om tokens te sparen maar om het antwoord bruikbaar te houden: een lijst van 90
documenten bij clausule 5.1 levert een antwoord dat alles noemt en niets aanwijst. De
grens wordt gemeld in het antwoordrecord, want een stille afkapping leest als volledigheid.
"""

MAX_BEVINDINGEN = 12
MAX_OPVOLGPUNTEN = 12

_CLAUSULE = re.compile(r"\b(\d{1,2}(?:\.\d{1,2}){1,3})\b")
"""Clausule-ID's zoals `8.24`, `9.2.2`, `A.5.7.1`. Minstens één punt, want een los getal in
een vraag is vaker een jaartal of een aantal dan een clausule."""


@dataclass(frozen=True)
class Bron:
    """Eén bron-record dat aan het model meegaat en in de trail belandt.

    `id` is wat het antwoord mag noemen en wat de verwijzingscontrole naloopt. De link gaat
    naar het landschapsscherm en niet naar Drive: de auditor hoort het document te openen
    via het spoor dat het tool zelf heeft vastgelegd.
    """

    soort: str  # 'document' | 'bevinding' | 'opvolgpunt' | 'normtekst'
    id: str
    naam: str
    clausules: tuple[str, ...] = ()
    samenvatting: str = ""
    link: str = ""

    def als_record(self) -> dict[str, Any]:
        return {
            "soort": self.soort,
            "id": self.id,
            "naam": self.naam,
            "clausules": list(self.clausules),
            "link": self.link,
        }


@dataclass
class Corpus:
    """Wat de assistent bij deze vraag kon zien.

    `afgekapt` houdt per soort bij dat er meer was dan de bovengrens. Dat hoort in het
    antwoord en in de trail: een lijst die stil op twaalf stopt leest als "dit is alles".
    """

    bronnen: list[Bron] = field(default_factory=list)
    clausules_in_vraag: tuple[str, ...] = ()
    via_clausule: bool = False
    afgekapt: dict[str, int] = field(default_factory=dict)

    @property
    def ids(self) -> set[str]:
        return {b.id for b in self.bronnen}

    @property
    def genoemde_clausules(self) -> set[str]:
        return {c for b in self.bronnen for c in b.clausules}

    def is_leeg(self) -> bool:
        return not self.bronnen


def clausules_uit(vraag: str) -> tuple[str, ...]:
    """Clausule-ID's uit de vraag, in de volgorde waarin ze voorkomen, zonder duplicaten."""
    gezien: list[str] = []
    for treffer in _CLAUSULE.findall(vraag):
        if treffer not in gezien:
            gezien.append(treffer)
    return tuple(gezien)


def _fts_query(vraag: str) -> str:
    """Bouw een FTS5-query uit de vraag.

    Alleen woorden van drie letters of meer, als OR-reeks. Bewust geen FTS5-operatoren
    doorlaten: een vraagteken of aanhalingsteken uit een gebruikersvraag maakt anders een
    syntaxfout van de query, en dat leest in de UI als "geen resultaten".
    """
    woorden = [w for w in re.findall(r"[\w-]{3,}", vraag.lower()) if not w.isdigit()]
    return " OR ".join(woorden)


def _documenten_via_clausule(
    conn: sqlite3.Connection, clausules: tuple[str, ...]
) -> list[sqlite3.Row]:
    plaatshouders = ",".join("?" for _ in clausules)
    # Alléén de gegenereerde `?`-plaatshouders gaan de query in; elke waarde gaat gebonden
    # mee. Zelfde patroon als in `verify_docs.py`.
    sql = (
        "SELECT d.id, d.naam, d.herkomst, "
        "GROUP_CONCAT(DISTINCT cm.clausule_id) AS clausules "
        "FROM clause_matches cm JOIN documents d ON d.id = cm.doc_id "
        f"WHERE cm.clausule_id IN ({plaatshouders}) "  # nosec B608
        "GROUP BY d.id, d.naam, d.herkomst ORDER BY d.naam LIMIT ?"
    )
    rijen: list[sqlite3.Row] = conn.execute(sql, (*clausules, MAX_DOCUMENTEN + 1)).fetchall()
    return rijen


def _documenten_via_tekst(conn: sqlite3.Connection, vraag: str) -> list[sqlite3.Row]:
    query = _fts_query(vraag)
    if not query:
        return []
    try:
        rijen: list[sqlite3.Row] = conn.execute(
            """
            SELECT d.id, d.naam, d.herkomst, '' AS clausules
            FROM documents_fts f
            JOIN documents d ON d.rowid = f.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, MAX_DOCUMENTEN + 1),
        ).fetchall()
    except sqlite3.OperationalError:
        # Een onbruikbare FTS-query is geen leeg corpus. Doorgeven als geen treffers zou
        # hetzelfde beeld geven als "niets gevonden", en dat is een ander antwoord.
        raise
    return rijen


def _bevindingen(
    conn: sqlite3.Connection, clausules: tuple[str, ...], doc_ids: list[str]
) -> list[sqlite3.Row]:
    """Bevindingen bij de clausules uit de vraag, en bij de gevonden documenten.

    Beide, want de tegenspraak die deze assistent moet kunnen tonen zit juist tussen een
    document dat dekking claimt en een eerdere bevinding op dezelfde clausule.
    """
    if not clausules and not doc_ids:
        return []
    voorwaarden: list[str] = []
    params: list[Any] = []
    if clausules:
        voorwaarden.append(f"clausule_id IN ({','.join('?' for _ in clausules)})")
        params.extend(clausules)
    if doc_ids:
        voorwaarden.append(f"doc_id IN ({','.join('?' for _ in doc_ids)})")
        params.extend(doc_ids)
    # Opvolgpunten staan in dezelfde tabel met herkomst `<bron>-opvolging`; die komen als
    # eigen soort mee en horen hier niet dubbel in.
    params.append(f"%{HERKOMST_ACHTERVOEGSEL}")
    params.append(MAX_BEVINDINGEN + 1)
    # Alleen gegenereerde plaatshouders in de query; waarden gaan gebonden mee.
    sql = (
        "SELECT id, doc_id, document_naam, clausule_id, norm, classificatie, "
        "beschrijving, classified_at FROM bevindingen "
        f"WHERE ({' OR '.join(voorwaarden)}) AND herkomst NOT LIKE ? "  # nosec B608
        "ORDER BY classified_at DESC LIMIT ?"
    )
    rijen: list[sqlite3.Row] = conn.execute(sql, params).fetchall()
    return rijen


def _opvolgpunten(conn: sqlite3.Connection, clausules: tuple[str, ...]) -> list[sqlite3.Row]:
    """Opvolgpunten uit de DB, niet live uit Jira.

    De pipeline legt ze bij een run vast; live ophalen zou een vraag laten hangen op een
    externe API en een ander corpus opleveren dan de run gebruikte.
    """
    if not clausules:
        return []
    plaatshouders = ",".join("?" for _ in clausules)
    # Alleen gegenereerde plaatshouders in de query; waarden gaan gebonden mee.
    sql = (
        "SELECT doc_id, document_naam, clausule_id, norm, beschrijving, herkomst "
        "FROM bevindingen "
        f"WHERE herkomst LIKE ? AND clausule_id IN ({plaatshouders}) "  # nosec B608
        "ORDER BY clausule_id LIMIT ?"
    )
    rijen: list[sqlite3.Row] = conn.execute(
        sql, (f"%{HERKOMST_ACHTERVOEGSEL}", *clausules, MAX_OPVOLGPUNTEN + 1)
    ).fetchall()
    return rijen


def _kap_af(rijen: list[sqlite3.Row], grens: int, soort: str, corpus: Corpus) -> list[sqlite3.Row]:
    if len(rijen) > grens:
        corpus.afgekapt[soort] = len(rijen) - grens
        return rijen[:grens]
    return rijen


def _normtekst_bronnen(clausules: tuple[str, ...], norm: str) -> list[Bron]:
    bronnen: list[Bron] = []
    for clausule in clausules:
        entry = normteksten.lookup(norm, clausule)
        if entry is None:
            continue
        bewijslast = entry.get("bewijslast") or []
        bronnen.append(
            Bron(
                soort="normtekst",
                id=f"norm:{norm}:{clausule}",
                naam=f"{norm} clausule {clausule} — {entry.get('titel', '')}".strip(" —"),
                clausules=(clausule,),
                # Interpretatie en bewijslast, niet de normtekst zelf: die is verkort
                # overgenomen en gaat niet letterlijk naar een gebruiker.
                samenvatting=" | ".join(
                    [str(entry.get("interpretatie", ""))]
                    + [f"verwacht bewijs: {b}" for b in bewijslast]
                ).strip(" |"),
            )
        )
    return bronnen


def haal_bronnen_op(conn: sqlite3.Connection, vraag: str, *, norm: str = "27001") -> Corpus:
    """Haal alles op wat bij deze vraag hoort — clausule eerst, dan tekst.

    Retourneert een `Corpus` met bron-records. Wat hier niet in zit, mag het antwoord niet
    noemen: de verwijzingscontrole in `vraag.py` loopt daarop na.
    """
    conn.row_factory = sqlite3.Row
    clausules = clausules_uit(vraag)
    corpus = Corpus(clausules_in_vraag=clausules, via_clausule=bool(clausules))

    doc_rijen = (
        _documenten_via_clausule(conn, clausules)
        if clausules
        else _documenten_via_tekst(conn, vraag)
    )
    doc_rijen = _kap_af(doc_rijen, MAX_DOCUMENTEN, "document", corpus)
    for r in doc_rijen:
        gekoppeld = tuple(sorted(filter(None, (r["clausules"] or "").split(","))))
        corpus.bronnen.append(
            Bron(
                soort="document",
                id=str(r["id"]),
                naam=str(r["naam"]),
                clausules=gekoppeld or clausules,
                link=f"#/landschap?doc={r['id']}",
            )
        )

    doc_ids = [str(r["id"]) for r in doc_rijen]
    bev_rijen = _kap_af(
        _bevindingen(conn, clausules, doc_ids), MAX_BEVINDINGEN, "bevinding", corpus
    )
    for b in bev_rijen:
        corpus.bronnen.append(
            Bron(
                soort="bevinding",
                id=f"bevinding:{b['id']}",
                naam=f"{b['classificatie']} op {b['clausule_id']} ({b['document_naam'] or '?'})",
                clausules=(str(b["clausule_id"]),),
                samenvatting=str(b["beschrijving"] or ""),
                link=f"#/landschap?clausule={b['clausule_id']}",
            )
        )

    for p in _kap_af(_opvolgpunten(conn, clausules), MAX_OPVOLGPUNTEN, "opvolgpunt", corpus):
        corpus.bronnen.append(
            Bron(
                soort="opvolgpunt",
                id=f"opvolgpunt:{p['doc_id']}",
                naam=str(p["document_naam"] or p["doc_id"]),
                clausules=(str(p["clausule_id"]),),
                samenvatting=str(p["beschrijving"] or ""),
            )
        )

    corpus.bronnen.extend(_normtekst_bronnen(clausules, norm))
    return corpus
