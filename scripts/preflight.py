"""Elke component lokaal aantoonbaar werkend, vóór er een image wordt gebouwd.

## Waarom dit bestaat

Op 21 augustus 2026 zijn vijf defecten in productie gevonden die geen van de 1159 tests kon
zien, omdat ze alle vijf pas optreden tegen de echte bronnen of in de echte procesvorm:

| defect | wat de suite niet zag |
|---|---|
| classificatie strandde op 63 clausules | de SDK weigert boven 21.333 tokens; een stub niet |
| stap 7/7 viel om op `NoneType < str` | Drive geeft niet voor élk bestand een `modifiedTime` |
| planning deed duizenden Sheets-calls | een N+1 valt alleen op tegen een echt quotum |
| docx zonder tekst heette "scan" | de fixture had tekst; het echte bestand had screenshots |
| vier startknoppen → SIGSEGV | één gedeelde client, alleen zichtbaar bij twee runs tegelijk |

Elk defect kostte een uitrol, en drie ervan kostten een halve auditrun. Vandaar deze
preflight: **per component één keer het echte pad aflopen**, lokaal, vóór de build.

## Wat het is en niet is

Geen vervanging van de testsuite — die blijft de gedragsgaranties. Dit is de laag eronder:
werkt de koppeling, komt er inhoud uit, houdt de vorm het vol tegen de echte data.

Read-only waar het kan. De audit-DB gaat naar een tijdelijk pad (`AUDIT_DB_PATH`), dus een
preflight raakt nooit de echte trail — dezelfde regel als voor de testsuite.

De classificatie kost geld en staat daarom **standaard uit**. Eén document, één clausule is
ongeveer $0,001; dat is de goedkoopste manier om te zien of het hele API-pad werkt inclusief
streaming en budget.

Writes: read-only op alle bronnen; schrijft alleen in een tijdelijke map.
Idempotent: ja.
Requires: `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`, en per component de bijbehorende
configuratie (`AUDIT_SOURCE_FOLDER_ID`, `PLANNING_SHEETS_ID`, `JIRA_*`, `ANTHROPIC_API_KEY`).
Een component zonder configuratie wordt **overgeslagen en gemeld**, niet stil groen.

## Waar de configuratie vandaan komt

Twee lagen, dezelfde als het portaal: het omgevingsbestand van deze machine, en daarna de
**bron-configuratie** die het configuratiescherm beheert (`bron_config.json` naast de
audits-map). Die tweede laag is het punt — de Anthropic-key en de Drive-locaties worden via
de UI ingevuld en staan niet in de shell-omgeving. Zonder die laag test een preflight met een
ándere configuratie dan een run, en dan zegt "lokaal groen" niets over online.

Geef `--config-root <audits-map>` mee of zet `ISO_AUDIT_AUDITS_ROOT`; zonder een van de twee
meldt de preflight dat alleen de shell-omgeving geldt.

Usage:
  uv run python scripts/preflight.py                        # alles behalve de betaalde
  uv run python scripts/preflight.py --component drive      # één component
  uv run python scripts/preflight.py --met-api              # inclusief classificatie (~$0,001)
  uv run python scripts/preflight.py --lijst                # welke componenten er zijn

Exitcode 0 als elke gedraaide component slaagde, 1 als er één faalde. Overgeslagen
componenten falen niet, maar staan wel in het overzicht — een build met een overgeslagen
component is een bewuste keuze, geen ongeluk.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("preflight")

MAX_TEKST_STEEKPROEF = 3
"""Hoeveel documenten er echt gelezen worden bij de Drive-check.

Niet alle 500: dat duurt tien minuten en de vraag is of het pad werkt, niet of elk bestand
leesbaar is. Drie is genoeg om een export, een download en een binaire lezer te raken."""


class OvergeslagenError(Exception):
    """Deze component kan niet draaien omdat zijn configuratie ontbreekt.

    Een eigen soort, want dit is geen falen: op een machine zonder Jira-token is "Jira
    overgeslagen" de juiste uitkomst. Stil groen melden zou het wél tot falen maken."""


@dataclass
class Uitkomst:
    naam: str
    status: str  # 'ok' | 'fout' | 'overgeslagen'
    detail: str
    seconden: float


def _vereis(*namen: str) -> None:
    """Raise `OvergeslagenError` als een van deze env-vars leeg is."""
    leeg = [n for n in namen if not os.environ.get(n)]
    if leeg:
        raise OvergeslagenError(f"niet geconfigureerd: {', '.join(leeg)}")


# --- componenten -----------------------------------------------------------


def check_drive() -> str:
    """Lijsten, dekking tellen, en een steekproef écht lezen.

    De steekproef is het punt: `list_documents` zegt alleen dat een bestand ondersteund
    heet. Of er tekst uit komt, blijkt pas bij lezen — en juist daar zaten de docx- en
    PDF-defecten.
    """
    _vereis("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE")
    from iso_audit.sources.drive import DriveSource, LeegDocumentError

    bron = DriveSource()
    docs = list(bron.list_documents())
    if not docs:
        raise RuntimeError("nul documenten uit de gekoppelde locaties")

    gelezen = 0
    leeg = 0
    for doc in docs[:MAX_TEKST_STEEKPROEF]:
        try:
            tekst = bron.fetch_content(doc)
        except LeegDocumentError:
            leeg += 1
            continue
        if tekst.strip():
            gelezen += 1
    per_type: dict[str, int] = {}
    for d in docs:
        per_type[d.type] = per_type.get(d.type, 0) + 1
    soorten = ", ".join(f"{k}={v}" for k, v in sorted(per_type.items()))
    return (
        f"{len(docs)} leesbare documenten ({soorten}); steekproef {gelezen} met tekst, {leeg} leeg"
    )


def check_planning() -> str:
    """Alle tabs in één leesronde — de N+1 die duizenden Sheets-calls deed."""
    _vereis("GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE")
    from iso_audit.clients import google_sheets
    from iso_audit.sources.planning import PlanningSource

    aanroepen = 0
    echt = google_sheets.sheets_lees_alle_tabs

    def _geteld(sid: str) -> dict[str, list[list[object]]]:
        nonlocal aanroepen
        aanroepen += 1
        return echt(sid)

    import iso_audit.sources.planning as planning_mod

    planning_mod.sheets_lees_alle_tabs = _geteld  # type: ignore[assignment]
    try:
        bron = PlanningSource()
        docs = list(bron.list_documents())
        for doc in docs[:MAX_TEKST_STEEKPROEF]:
            bron.fetch_content(doc)
    finally:
        planning_mod.sheets_lees_alle_tabs = echt  # type: ignore[assignment]

    if aanroepen > 1:
        raise RuntimeError(
            f"spreadsheet {aanroepen}x gelezen voor {len(docs)} documenten; "
            "de momentopname per instantie werkt niet"
        )
    return f"{len(docs)} planning-rijen, spreadsheet 1x gelezen"


def check_nextcloud() -> str:
    """WebDAV-listing en een steekproef écht lezen, tegen een echte server.

    Gedraaid tegen `canary-accept/nextcloud` (32.0.13) op 2026-08-22. Die run vond meteen twee
    fouten die de gestubde tests niet zagen: paden werden relatief aan de opgevraagde map
    teruggegeven (waardoor de recursie in de verkeerde map zocht), en een lege `.txt` kreeg de
    melding "mogelijk staat de inhoud in tekstvakken" — over een bestand van nul bytes.
    """
    _vereis("NEXTCLOUD_BASE_URL", "NEXTCLOUD_USER", "NEXTCLOUD_APP_PASSWORD")
    from iso_audit.sources.nextcloud import NextcloudSource
    from iso_audit.sources.tekst import LeegDocumentError

    bron = NextcloudSource()
    status = bron.probe()
    if status["status"] != "ok":
        raise RuntimeError(f"probe faalde: {status.get('reden')}")

    docs = list(bron.list_documents())
    if not docs:
        raise RuntimeError("nul documenten uit de geconfigureerde paden")

    gelezen = 0
    leeg = 0
    for doc in docs[:MAX_TEKST_STEEKPROEF]:
        try:
            if bron.fetch_content(doc).strip():
                gelezen += 1
        except LeegDocumentError:
            leeg += 1

    dekking = bron.dekking()
    som = dekking["gelezen"] + sum(dekking["overgeslagen"].values())
    if som != dekking["gezien"]:
        raise RuntimeError(
            f"dekking telt niet op: gezien {dekking['gezien']} ≠ gelezen "
            f"{dekking['gelezen']} + overgeslagen {sum(dekking['overgeslagen'].values())}"
        )
    per_type: dict[str, int] = {}
    for d in docs:
        per_type[d.type] = per_type.get(d.type, 0) + 1
    soorten = ", ".join(f"{k}={v}" for k, v in sorted(per_type.items()))
    return (
        f"{len(docs)} documenten ({soorten}); steekproef {gelezen} met tekst, {leeg} leeg; "
        f"dekking {dekking['gezien']} gezien / {dekking['gelezen']} gelezen"
    )


def check_jira() -> str:
    """Opvolgpunten ophalen — en vaststellen dat ze buiten de triage blijven."""
    _vereis("JIRA_BASE_URL", "JIRA_API_TOKEN")
    # De adapters registreren zich via side-effect-imports in `beschikbare_bronnen()`;
    # zonder die aanroep is de registry leeg en meldt élke bron zich als onbekend. Het
    # portaal doet dit in `valideer_bronselectie`. De eerste echte preflight (2026-08-22)
    # liep hier stuk — een terechte fout in de check, en tegelijk een aanwijzing dat die
    # registratie aan een functienaam hangt die niet zegt dat hij registreert.
    from iso_audit.ingest import beschikbare_bronnen
    from iso_audit.sources.opvolgpunten import haal_op, levert_opvolgpunten

    bekend = beschikbare_bronnen()
    if "jira" not in bekend:
        raise RuntimeError(f"jira staat niet in de registry; beschikbaar: {sorted(bekend)}")
    if not levert_opvolgpunten("jira"):
        raise RuntimeError("jira meldt zich niet als leverancier van opvolgpunten")
    punten = haal_op("jira", "preflight")
    herkomsten = {str(p.get("herkomst", "")) for p in punten}
    fout = [h for h in herkomsten if not h.endswith("-opvolging")]
    if fout:
        raise RuntimeError(
            f"herkomst zonder -opvolging-achtervoegsel: {fout}; die zouden in de triage "
            "belanden als bewijs in plaats van als bewijslast"
        )
    return f"{len(punten)} opvolgpunten, herkomst {sorted(herkomsten) or '—'}"


def check_landschap() -> str:
    """Documenten wegschrijven en terugzoeken via FTS5 — het pad dat de assistent gebruikt."""
    from iso_audit.store import initialiseer, upsert_document, verbinding, zoek

    conn = verbinding()
    initialiseer(conn)
    upsert_document(
        conn,
        {
            "id": "preflight-1",
            "naam": "Cryptobeleid preflight.docx",
            "tekst": "sleutelbeheer en algoritmen voor preflight",
            "herkomst": "Drive",
            "mime_type": "text/plain",
            # None en geen "": Drive levert dit veld niet altijd, en juist die None sloopte
            # stap 7/7 op 2026-08-21.
            "modified_at": None,
        },
    )
    treffers = zoek(conn, "preflight")
    conn.close()
    if not treffers:
        raise RuntimeError("FTS5 vond het net weggeschreven document niet")
    return f"{len(treffers)} treffer(s) via FTS5; modified_at=None gaf geen fout"


def check_assistent() -> str:
    """De Bronbevrager: leeg corpus bevraagt geen model, en de merktekenregels kloppen.

    De echte-model-variant zit in `--met-api`; deze check dekt wat zonder kosten te
    bewijzen valt en juist op 2026-08-22 fout was: een eerlijk "niet gevonden" werd door de
    verwijzingscontrole geweigerd.
    """
    from iso_audit.assistent import vraag as assistent
    from iso_audit.store import initialiseer, verbinding

    conn = verbinding()
    initialiseer(conn)

    class _Weigert:
        messages = None

        def create(self, **kw: object) -> object:
            raise AssertionError("er mag geen model bevraagd zijn zonder bronnen")

    uit = assistent.beantwoord(conn, "Wat is de beste encryptie?", client=_Weigert())
    if not uit.geen_dekking:
        raise RuntimeError("leeg corpus leverde geen 'staat er niet in'")

    # Het merkteken moet een antwoord zonder verwijzing geldig maken, en niets anders.
    from iso_audit.assistent.ophalen import Corpus

    leeg = Corpus()
    if assistent.verifieer_verwijzingen(f"niets {assistent.NIETS_GEVONDEN}", leeg) != []:
        raise RuntimeError("merkteken levert onverwachte bron-ID's op")
    try:
        assistent.verifieer_verwijzingen("Ja, dat is geregeld.", leeg)
    except assistent.AntwoordOnverifieerbaarError:
        pass
    else:
        raise RuntimeError("bewering zonder verwijzing én zonder merkteken werd geaccepteerd")
    conn.close()
    return "leeg corpus → geen API-aanroep; merkteken-regels kloppen"


def check_rapport() -> str:
    """Rapport schrijven met de vorm die stap 7/7 twee keer sloopte."""
    from iso_audit.reporting.local_report import schrijf_rapport

    pad = schrijf_rapport(
        bevindingen=[
            {
                "clausule": "8.24",
                "norm": "27001",
                "classificatie": "NC",
                "beschrijving": "preflight",
                "onderbouwing": "preflight",
                "document_naam": "Cryptobeleid.docx",
                "doc_id": "d1",
                "herkomst": "Drive",
            }
        ],
        ontbrekende_clausules=[],
        handmatige_review=[],
        management_summary="preflight",
        norm="27001",
        output_dir=str(Path(os.environ["PREFLIGHT_UIT"]) / "rapport"),
        # Precies de vorm die op 2026-08-21 `'<' not supported between NoneType and str` gaf:
        # Drive geeft niet voor élk bestand een modifiedTime.
        gearchiveerd=[
            {"id": "a1", "naam": "Met datum", "modified_at": "2023-01-15T10:00:00Z"},
            {"id": "a2", "naam": "Zonder datum", "modified_at": None},
            {"id": "a3", "naam": "Sleutel ontbreekt"},
        ],
    )
    tekens = len(Path(pad).read_text(encoding="utf-8"))
    return f"rapport geschreven ({tekens} tekens), incl. archief zonder datum"


def check_classificatie() -> str:
    """Eén echte API-call: streaming, budget en parsing in één keer. Kost ~$0,001."""
    _vereis("ANTHROPIC_API_KEY")
    import anthropic

    from iso_audit.classification.findings import (
        SDK_NIET_STREAMEND_PLAFOND,
        Kostenteller,
        _classificeer_doc,
        _max_tokens_voor,
    )

    # Een clausule-aantal boven het SDK-plafond: niet-streamend raist dit een ValueError.
    zwaar = SDK_NIET_STREAMEND_PLAFOND // 450 + 2
    if _max_tokens_voor(zwaar) <= SDK_NIET_STREAMEND_PLAFOND:
        raise RuntimeError("plafondberekening klopt niet; check _max_tokens_voor")

    teller = Kostenteller()
    doc = {
        "naam": "Preflight cryptobeleid.docx",
        "tekst": "Wij versleutelen data in rust met AES-256 en beheren sleutels in een kluis.",
    }
    uit = _classificeer_doc(
        doc,
        ["8.24"],
        {"8.24": {"titel": "Gebruik van cryptografie"}},
        anthropic.Anthropic(),
        teller,
    )
    if teller.fouten:
        raise RuntimeError(f"{teller.fouten} fout(en) in één classificatie")
    return (
        f"{len(uit)} bevinding(en), ${teller.kosten_usd():.4f}, "
        f"budget bij {zwaar} clausules = {_max_tokens_voor(zwaar)} (streamend vereist)"
    )


def check_assistent_api() -> str:
    """De Bronbevrager tegen het echte model, op het echte corpus. Kost ~$0,01.

    Dit is de check die op 2026-08-22 als enige de fout vond die alle 1159 tests misten: een
    eerlijk "niet gevonden" heeft geen bron om naar te verwijzen, en de verwijzingscontrole
    weigerde daarom twee van de drie antwoorden. Zonder een echte vraag op een echt corpus
    komt dat niet boven water — een stub antwoordt wat de test wil.
    """
    _vereis("ANTHROPIC_API_KEY")
    import sqlite3

    from iso_audit.assistent import vraag as assistent
    from iso_audit.store import verbinding

    conn = verbinding(os.environ.get("PREFLIGHT_CORPUS") or None)
    conn.row_factory = sqlite3.Row
    try:
        aantal = conn.execute("SELECT COUNT(*) FROM clause_matches").fetchone()[0]
    except sqlite3.OperationalError as e:
        raise OvergeslagenError(f"geen corpus om op te vragen: {e}") from e
    if not aantal:
        raise OvergeslagenError("corpus is leeg; zet PREFLIGHT_CORPUS op een DB met clause_matches")

    clausule = str(conn.execute("SELECT clausule_id FROM clause_matches LIMIT 1").fetchone()[0])
    met = assistent.beantwoord(conn, f"Welk bewijs hebben wij voor {clausule}?")
    zonder = assistent.beantwoord(
        conn, f"Staat er iets over onze cateringleverancier in {clausule}?"
    )
    conn.close()

    # De invariant is niet "er komen verwijzingen uit" — of het corpus die vraag beantwoordt,
    # ligt aan het corpus. De invariant is dat de auditor **nooit onverifieerbare prose ziet**:
    # elk antwoord verwijst, óf is vervangen door de vaste tekst, óf had geen bronnen.
    for label, uit in (("met dekking", met), ("zonder dekking", zonder)):
        veilig = bool(uit.gebruikt) or uit.onverifieerbaar or uit.geen_dekking
        if not veilig:
            raise RuntimeError(f"vraag {label}: antwoord zonder verwijzing én niet vervangen")
        if uit.onverifieerbaar and uit.antwoord != assistent.ONVERIFIEERBAAR:
            raise RuntimeError(f"vraag {label}: onverifieerbaar maar toont eigen tekst")

    hoe = "met verwijzing" if met.gebruikt else "vervangen (bronnen beantwoorden de vraag niet)"
    return (
        f"clausule {clausule}: {len(met.meegegeven)} bronnen, {len(met.gebruikt)} gebruikt "
        f"({hoe}); tweede vraag "
        f"{'vervangen' if zonder.onverifieerbaar else 'met verwijzing'}; "
        f"${met.usd + zonder.usd:.4f}"
    )


def check_triage_agent() -> str:
    """De clausule-agent tegen het echte model en corpus. Kost ~$0,01.

    Deze check bestaat omdat de eerste echte run (2026-08-22) een fout vond die geen enkele
    gestubde test kon zien: het model levert één rij per bron, dus een bewijslast-item dat door
    vijf documenten wordt gedekt gaf vijf rijen — en clausule 9.2 meldde "2 van 8
    bewijsstukken niet gevonden" terwijl de norm er vier kent.
    """
    _vereis("ANTHROPIC_API_KEY")
    import sqlite3

    from iso_audit.assistent import clausule as ca
    from iso_audit.store import verbinding

    conn = verbinding(os.environ.get("PREFLIGHT_CORPUS") or None)
    conn.row_factory = sqlite3.Row
    try:
        # `norm` is in `clause_matches` ook `beide` — een clausule die in allebei de normen
        # bestaat. Die uitsluiten leverde "corpus bevat geen clause_matches" op een corpus met
        # 3337 rijen; de melding klopte niet en de check draaide niet.
        rij = conn.execute(
            "SELECT clausule_id, norm FROM clause_matches "
            "WHERE norm IN ('9001','27001','beide') LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError as e:
        raise OvergeslagenError(f"geen corpus om op te vragen: {e}") from e
    if rij is None:
        raise OvergeslagenError("corpus bevat geen bruikbare clause_matches")

    # Een clausule **met** bewijslast: zonder bewijslast bevraagt de agent geen model, en dan
    # slaagt deze check leeg. Gemeten op 2026-08-22: de eerste clausule uit `clause_matches`
    # (4.4) heeft er geen, en de check meldde "0 bewijslast-items, $0.0000" als OK.
    from iso_audit.data import normteksten

    kandidaat: tuple[str, str] | None = None
    for r in conn.execute(
        "SELECT DISTINCT clausule_id, norm FROM clause_matches "
        "WHERE norm IN ('9001','27001','beide')"
    ).fetchall():
        # `beide` is geen norm die `normteksten` kent; 27001 is dan de bredere catalogus.
        n = str(r["norm"]) if str(r["norm"]) in ("9001", "27001") else "27001"
        entry = normteksten.lookup(n, str(r["clausule_id"])) or {}
        if entry.get("bewijslast"):
            kandidaat = (str(r["clausule_id"]), n)
            break
    if kandidaat is None:
        raise OvergeslagenError("geen gekoppelde clausule met bewijslast in de catalogus")

    beeld = ca.bekijk(conn, kandidaat[0], norm=kandidaat[1])
    conn.close()

    if set(beeld.als_record()) & ca.VERBODEN_VELDEN:
        raise RuntimeError("de agent leverde een oordeelsveld; die grens moet dicht blijven")
    items = beeld.gedekte_items | beeld.open_items
    if not items:
        raise RuntimeError("clausule met bewijslast leverde geen enkel item op")
    if len(items) > len(beeld.bewijs_aanwezig) + len(beeld.bewijs_ontbreekt):
        raise RuntimeError("meer verschillende items dan rijen; dat kan niet")
    return (
        f"clausule {beeld.clausule_id}: {len(beeld.meegegeven)} bronnen, "
        f"{len(items)} bewijslast-items, dekking {beeld.dekkingsgraad:.0%}, ${beeld.usd:.4f}"
    )


COMPONENTEN: dict[str, Callable[[], str]] = {
    "landschap": check_landschap,
    "rapport": check_rapport,
    "assistent": check_assistent,
    "drive": check_drive,
    "planning": check_planning,
    "jira": check_jira,
    "nextcloud": check_nextcloud,
    "classificatie": check_classificatie,
    "assistent-api": check_assistent_api,
    "triage-agent": check_triage_agent,
}
"""Volgorde is bewust: eerst wat geen netwerk vraagt, dan de bronnen, dan wat geld kost.
Zo faalt een preflight op een tikfout binnen een seconde in plaats van na tien minuten."""

BETAALD = frozenset({"classificatie", "assistent-api", "triage-agent"})
"""Componenten die de Claude-API raken. Alleen met `--met-api`."""


def _laad_configuratie(config_root: str | None) -> None:
    """Vul `os.environ` langs dezelfde weg als het portaal, en meld waaruit.

    Twee lagen, in de volgorde die het portaal ook aanhoudt:

    1. Het omgevingsbestand van deze machine, via `load_dotenv()` — wat een beheerder hier
       heeft gezet.
    2. De **bron-configuratie** die het portaal zelf beheert (`bron_config.json` naast de
       audits-map, geschreven door het configuratiescherm). `naar_omgeving()` overschrijft
       geen bestaande waarden behalve expliciete overschrijvingen — dezelfde precedentie als
       in het portaal.

    Waarom die tweede laag hier hoort: zonder haar test een preflight met een ándere
    configuratie dan een run, en dan is "lokaal groen" geen uitspraak over online. Gemeten
    geval op 2026-08-22: de Anthropic-key en de Drive-locaties worden via het
    configuratiescherm ingevuld, dus de classificatie-check werd lokaal overgeslagen terwijl
    hij in het cluster gewoon werkt.

    Meldt welke laag iets opleverde. Een preflight die stil een lege configuratie gebruikt,
    beantwoordt de verkeerde vraag.
    """
    from dotenv import load_dotenv

    load_dotenv()

    root = config_root or os.environ.get("ISO_AUDIT_AUDITS_ROOT")
    if not root:
        print(
            "geen bron-configuratie geladen — zet ISO_AUDIT_AUDITS_ROOT of geef "
            "--config-root mee; nu geldt alleen de omgeving van deze shell",
            file=sys.stderr,
        )
        return
    from iso_audit.api.bron_config import BronConfig

    # `.parent`: `bron_config.json` staat náást de audits-map, niet erin — zelfde afleiding
    # als in `create_app`.
    winkel = BronConfig(Path(root).parent)
    voor = set(os.environ)
    winkel.naar_omgeving()
    erbij = sorted(set(os.environ) - voor)
    plek = Path(root).parent
    print(f"bron-configuratie uit {plek}: {', '.join(erbij) if erbij else 'niets toegevoegd'}")


def _draai(naam: str) -> Uitkomst:
    begin = time.monotonic()
    try:
        detail = COMPONENTEN[naam]()
    except OvergeslagenError as e:
        return Uitkomst(naam, "overgeslagen", str(e), time.monotonic() - begin)
    except Exception as e:  # een preflight moet élke fout rapporteren, niet alleen bekende
        logger.debug("%s faalde:\n%s", naam, traceback.format_exc())
        return Uitkomst(naam, "fout", f"{type(e).__name__}: {e}", time.monotonic() - begin)
    return Uitkomst(naam, "ok", detail, time.monotonic() - begin)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__ or "", add_help=True)
    parser.add_argument("--component", action="append", help="alleen deze component(en)")
    parser.add_argument("--met-api", action="store_true", help="ook de betaalde checks")
    parser.add_argument("--lijst", action="store_true", help="toon de componenten en stop")
    parser.add_argument(
        "--config-root",
        help=(
            "audits-map waarvan de bron-configuratie geladen wordt "
            "(default: $ISO_AUDIT_AUDITS_ROOT)"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="tracebacks in het log")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    if args.lijst:
        for naam in COMPONENTEN:
            merk = " (betaald)" if naam in BETAALD else ""
            print(f"  {naam}{merk}")
        return 0

    gekozen = args.component or list(COMPONENTEN)
    onbekend = [n for n in gekozen if n not in COMPONENTEN]
    if onbekend:
        print(f"onbekende component(en): {', '.join(onbekend)}", file=sys.stderr)
        return 2
    if not args.met_api:
        gekozen = [n for n in gekozen if n not in BETAALD]

    _laad_configuratie(args.config_root)

    # Eigen DB en eigen uitvoermap: een preflight mag de echte trail nooit raken. Zelfde
    # regel als voor de testsuite, en om dezelfde reden — de fout zou stil zijn.
    with tempfile.TemporaryDirectory(prefix="iso-preflight-") as tmp:
        os.environ["AUDIT_DB_PATH"] = str(Path(tmp) / "preflight.db")
        os.environ["PREFLIGHT_UIT"] = tmp
        uitkomsten = [_draai(naam) for naam in gekozen]

    breedte = max(len(u.naam) for u in uitkomsten)
    print()
    for u in uitkomsten:
        merk = {"ok": "OK  ", "fout": "FOUT", "overgeslagen": "OVER"}[u.status]
        print(f"{merk}  {u.naam.ljust(breedte)}  {u.seconden:5.1f}s  {u.detail}")

    fout = [u.naam for u in uitkomsten if u.status == "fout"]
    over = [u.naam for u in uitkomsten if u.status == "overgeslagen"]
    niet_gedraaid = [n for n in COMPONENTEN if n not in gekozen]
    print()
    if over:
        print(f"overgeslagen (geen configuratie): {', '.join(over)}")
    if niet_gedraaid:
        print(f"niet gedraaid: {', '.join(niet_gedraaid)}")
    if fout:
        print(f"FAALT: {', '.join(fout)}")
        return 1
    print("alle gedraaide componenten in orde")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
