"""Orchestrator: ISO audit pipeline.

Gemigreerd uit `Ops_to_Biz/audit/pipeline.py` per milestone B §2.5.10.
Wijzigingen: imports vernieuwd naar `iso_audit.*`; type-hints aangevuld
voor mypy --strict; CLI ondersteunt optionele `argv` voor tests;
`subprocess` voor `gws auth status` gebruikt bandit-nosec markers.

Gebruik:
    python -m iso_audit.pipeline --norm 9001
    python -m iso_audit.pipeline --norm 27001
    python -m iso_audit.pipeline --norm beide

    # Eén hoofdstuk uitvoeren (minder API-calls, sneller):
    python -m iso_audit.pipeline --norm 9001 --chapter 4
    python -m iso_audit.pipeline --norm beide --chapter 8

    # Dry-run zonder externe verbindingen (test + lokale output):
    python -m iso_audit.pipeline --local-only --norm 9001

    # Alleen template aanmaken (eerste keer):
    python -m iso_audit.pipeline --setup-template

Omgevingsvariabelen: zie .env.example.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess  # nosec B404 — gws CLI is een gecontroleerde shell-laag
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

if TYPE_CHECKING:
    from iso_audit.modes.base import Mode

load_dotenv()

logger = logging.getLogger(__name__)


def _maak_audit_id() -> str:
    """UTC-tijdstempel-gebaseerde run-id voor `decisions`/`classifications`."""
    return f"audit-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def _emit_decision(
    mode: Mode | None,
    punt: str,
    voorstel: dict[str, Any],
    risico: str = "laag",
    context: dict[str, Any] | None = None,
    audit_id: str = "",
) -> dict[str, Any]:
    """Stuur een Decision naar de actieve Mode en retourneer het besluit.

    Als `mode` `None` is (legacy-pad, M-B-tijdperk), wordt het voorstel
    direct geretourneerd zonder DB-rij — equivalent aan AutonoomMode-
    laag/midden-gedrag.
    """
    if mode is None:
        return dict(voorstel)
    from iso_audit.modes.base import Decision

    decision = Decision(
        punt=punt,
        context=context or {},
        voorstel=voorstel,
        risico=risico,  # type: ignore[arg-type]
        audit_id=audit_id,
    )
    besluit = mode.beslis(decision)
    return dict(besluit)


def _resume_pending_decisions(audit_id: str, mode: Mode | None) -> None:
    """§3.1.8 — bij start: poll bestaande pending decisions tot resolved.

    Bij een crash kan een rij in `decisions` met `status='pending'`
    achterblijven. De pipeline-restart MOET die hervatten in plaats van
    opnieuw escaleren. Dit is een minimale implementatie: log de pending
    rijen zodat de operator weet dat ze bestaan. Volledige hervatting
    (resume polling op specifieke decision_id) komt mee met de
    pipeline-`audit_id`-persistentie in §3.6.
    """
    if mode is None:
        return
    from iso_audit.store import laad_pending_decisions, verbinding

    conn = verbinding()
    try:
        rijen = laad_pending_decisions(conn, audit_id)
    finally:
        conn.close()
    if rijen:
        logger.warning(
            "[crash-recovery] %d pending decisions gevonden voor audit %s — "
            "controleer eerst de auditor-respons voor: %s",
            len(rijen),
            audit_id,
            [r["punt"] for r in rijen],
        )


def _valideer_env() -> None:
    """Controleer dat gws beschikbaar en ingelogd is."""
    if not shutil.which("gws"):
        logger.error("gws CLI niet gevonden in PATH.")
        sys.exit(1)
    try:
        result = subprocess.run(  # nosec B603 — args zijn statisch
            ["gws", "auth", "status"],  # nosec B607
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        status = json.loads(result.stdout) if result.stdout.strip() else {}
        if not status.get("token_valid", False):
            logger.warning(
                "gws auth token niet geldig (%s). Voer `gws auth login` uit als API-calls falen.",
                status.get("token_error", "onbekend"),
            )
    except Exception:
        pass


_LOKALE_TEST_BEVINDINGEN: list[dict[str, Any]] = [
    {
        "clausule": "4.1",
        "clausule_titel": "Inzicht in de organisatie en haar context",
        "document_naam": "[TESTDATA] Contextanalyse_2025.docx",
        "herkomst": "Drive",
        "classificatie": "positief",
        "beschrijving": (
            "De organisatie heeft een gedocumenteerde contextanalyse "
            "uitgevoerd. Interne en externe factoren zijn beschreven."
        ),
        "onderbouwing": ("ISO 9001:2015 §4.1 vereist begrip van interne en externe context."),
        "pre_classificatie": None,
    },
    {
        "clausule": "5.2",
        "clausule_titel": "Beleid",
        "document_naam": "[TESTDATA] Kwaliteitsbeleid_v2.docx",
        "herkomst": "Drive",
        "classificatie": "OFI",
        "beschrijving": (
            "Het kwaliteitsbeleid is aanwezig maar wordt niet actief "
            "gecommuniceerd naar alle medewerkers."
        ),
        "onderbouwing": (
            "ISO 9001:2015 §5.2.2 vereist dat het beleid beschikbaar is "
            "als gedocumenteerde informatie."
        ),
        "pre_classificatie": None,
    },
    {
        "clausule": "8.1",
        "clausule_titel": "Operationele planning en beheersing",
        "document_naam": "[TESTDATA] Miro sticky: geen gedocumenteerd proces",
        "herkomst": "Miro",
        "classificatie": "NC",
        "beschrijving": (
            "Er is geen gedocumenteerde operationele planning voor het "
            "primaire proces aangetroffen."
        ),
        "onderbouwing": (
            "ISO 9001:2015 §8.1 vereist planning, implementatie en "
            "beheersing van operationele processen."
        ),
        "pre_classificatie": "rood",
    },
]

_LOKALE_TEST_ONTBREKEND: list[dict[str, Any]] = [
    {
        "clausule": "9.3",
        "titel": "Directiebeoordeling",
        "reden": "[TESTDATA] Geen bewijs van directiebeoordeling gevonden",
    },
]


def run_local_only(norm: str) -> str:
    """Dry-run: synthetische data → lokale Markdown + CSV + Excel."""
    from iso_audit.classification.thema import bepaal_thema
    from iso_audit.reporting.local_report import schrijf_rapport
    from iso_audit.reporting.tabular_report import schrijf_csv, schrijf_excel

    logger.info("=== ISO Audit Pipeline — LOCAL ONLY (testdata) ===")
    logger.info("Norm: %s | Geen Drive/Claude/Sheets-verbinding", norm)

    management_summary = (
        "**[TESTDATA]** Dit rapport is gegenereerd met synthetische "
        "testbevindingen zonder verbinding met Google Drive of de "
        "Claude API. Gebruik `--local-only` uitsluitend voor het testen "
        "van de rapportage-logica."
    )

    for bev in _LOKALE_TEST_BEVINDINGEN:
        bev.setdefault("thema", bepaal_thema(bev))

    lokaal_pad = schrijf_rapport(
        _LOKALE_TEST_BEVINDINGEN,
        _LOKALE_TEST_ONTBREKEND,
        [],
        management_summary,
        norm,
    )
    logger.info("Lokaal testrapport: %s", lokaal_pad)

    csv_pad = schrijf_csv(_LOKALE_TEST_BEVINDINGEN, norm)
    xlsx_pad = schrijf_excel(_LOKALE_TEST_BEVINDINGEN, norm)
    logger.info("Tabulair: %s  |  %s", csv_pad, xlsx_pad)

    return lokaal_pad


_RUIS_PATTERNS: tuple[str, ...] = (
    "VERWIJDEREN",
    "TEMPLATE KOPIE MAKEN",
)
_RUIS_PREFIXES: tuple[str, ...] = (
    "OUD:",
    "OUD ",
    "Oud:",
)


def _is_ruis(document_naam: str) -> bool:
    """Drive-rommel detector: documenten die niet in een auditrapport horen."""
    if not document_naam:
        return False
    naam = document_naam.strip()
    if any(p in naam for p in _RUIS_PATTERNS):
        return True
    return naam.startswith(_RUIS_PREFIXES)


def _filter_ruis(bevindingen: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Verwijder ruis-bevindingen; retourneer (schoon, aantal_geskipped)."""
    schoon = [b for b in bevindingen if not _is_ruis(b.get("document_naam", ""))]
    geskipped = len(bevindingen) - len(schoon)
    if geskipped:
        logger.info(
            "Ruis-filter: %d bevinding(en) uit Drive-archief weggelaten "
            "(VERWIJDEREN/TEMPLATE KOPIE MAKEN/OUD-prefix)",
            geskipped,
        )
    return schoon, geskipped


def run_setup_template() -> None:
    """Eénmalige setup: template aanmaken in Drive."""
    from iso_audit.reporting.template_setup import create_template, verify_placeholders

    folder_id = os.environ.get("AUDIT_DRIVE_FOLDER_ID", "")
    logger.info("Template aanmaken...")
    doc_id = create_template(folder_id)
    ontbrekend = verify_placeholders(doc_id)
    if ontbrekend:
        logger.warning("Voeg AUDIT_TEMPLATE_DOC_ID=%s toe aan .env", doc_id)
    else:
        logger.info("Template klaar. Voeg toe aan .env: AUDIT_TEMPLATE_DOC_ID=%s", doc_id)


def _bewaar_opvolgpunten(punten: list[dict[str, Any]], norm: str) -> None:
    """Leg openstaande punten vast als bewijs dat er opvolging plaatsvindt.

    Ze gaan in de `bevindingen`-tabel met herkomst `<bron>-opvolging`: één administratie,
    geen tweede tabel voor iets dat dezelfde vorm heeft (clausule, bron, beschrijving).

    **Maar niet naar de triage.** Hier stond dat een opvolgpunt "een punt is dat de auditor
    moet wegen", en dat is precies wat het niet is: het is al beoordeeld door degene die het
    aanmaakte. Wat het in een audit doet, is aantonen dát er opvolging is — bewijslast, geen
    bevinding. Op 2026-08-22 stonden er daardoor 83 Jira-punten in een werklijst van 901 met
    een triage-vraag die niemand kon beantwoorden. `export_db_findings` filtert ze eruit.
    """
    if not punten:
        return
    from iso_audit.classification.findings import _upsert_bevindingen
    from iso_audit.store import initialiseer, verbinding

    conn = verbinding()
    try:
        initialiseer(conn)
        _upsert_bevindingen(conn, punten, norm)
    finally:
        conn.close()


def _veilige_reden(exc: Exception, bron: str) -> str:
    """Genormaliseerde reden voor een mislukte bron-ingest.

    De ruwe melding kan een URL met credential of een responsbody bevatten; die hoort in
    het serverlog en niet in een run-record dat de browser toont.
    """
    from iso_audit.config.verbinding import normaliseer

    _, tekst = normaliseer(exc, bron=bron)
    return tekst


class BronIngestError(RuntimeError):
    """Eén of meer gekozen bronnen leverden niets door een fout.

    Wordt door `run_audit` gegooid nadat de rest van de ingest is vastgelegd, zodat de
    documenten die wél gelezen zijn bewaard blijven én de run niet ten onrechte `klaar`
    meldt. `bronnen` is per bron de genormaliseerde reden.
    """

    def __init__(self, bronnen: dict[str, str]) -> None:
        self.bronnen = bronnen
        deel = "; ".join(f"{n}: {r}" for n, r in sorted(bronnen.items()))
        super().__init__(f"Bron(nen) leverden niets: {deel}")


def _bewaar_ingest(documenten: list[dict[str, Any]], norm: str, bronnen: list[str]) -> None:
    """Leg de ingelezen documenten en hun clausule-koppelingen vast in de audit-DB.

    Idempotent (`upsert`), zodat een tweede run niets dupliceert. Fouten worden gelogd en
    niet doorgegooid: het vastleggen mag een run niet laten sneuvelen, en de documenten
    zitten op dat moment al in het geheugen van de lopende run.
    """
    from iso_audit.store import (
        initialiseer,
        log_ingest,
        upsert_clause_match,
        upsert_document,
        verbinding,
    )

    if not documenten:
        return
    try:
        conn = verbinding()
        initialiseer(conn)
        for doc in documenten:
            herkomst = doc.get("herkomst", "Drive")
            upsert_document(conn, doc)
            # `clausule_normen` draagt per match de norm waaruit hij komt; `norm` is de
            # run-parameter en kan `beide` zijn, wat geen norm van een clausule is.
            for clausule_id, match_norm in doc.get("clausule_normen", []):
                upsert_clause_match(conn, doc["id"], herkomst, clausule_id, match_norm or norm)
            for clausule_id, sub_punt_id in doc.get("sub_punt_matches", []):
                match_norm = next(
                    (n for c, n in doc.get("clausule_normen", []) if c == clausule_id), norm
                )
                upsert_clause_match(
                    conn, doc["id"], herkomst, clausule_id, match_norm or norm, sub_punt_id
                )
        conn.commit()
        log_ingest(conn, ",".join(bronnen), None, len(documenten))
        conn.commit()
        conn.close()
        logger.info("%d document(en) vastgelegd in de audit-DB", len(documenten))
    except Exception as exc:  # vastleggen mag de run niet breken
        logger.warning("Documenten vastleggen mislukt (run gaat door): %s", exc)


def run_audit(
    norm: str,
    no_review: bool = False,
    write_sheets: bool = False,
    chapter: str | None = None,
    scherpte: float = 1.0,
    thema_llm: bool = False,
    rehash: bool = False,
    review: bool | None = None,
    review_steekproef: int = 0,
    auto_triage: bool | None = None,
    dry_run_cost: bool = False,
    mode: Mode | None = None,
    audit_id: str | None = None,
    sources: list[str] | None = None,
    alleen_ingest: bool = False,
    op_kosten: Callable[[Any], None] | None = None,
    op_dekking: Callable[[Any], None] | None = None,
) -> None:
    """Volledige auditpipeline uitvoeren.

    :param op_dekking: Krijgt de Drive-dekkingtelling na de ingest (gezien, gelezen, en per
        reden overgeslagen), zodat de caller die in het run-record kan zetten. Zelfde vorm
        als `op_kosten`.

    :param alleen_ingest: Stop na stap 4 (inlezen + clausule-koppeling + vastleggen).
        Raakt de Claude-API niet en werkt dus zonder API-key. Bedoeld om de keten naar de
        bronnen te kunnen verifiëren los van de classificatie, en om een dure Drive-lezing
        niet te verspillen wanneer de classificatie nog niet kan draaien.

    :param mode: Actieve :class:`iso_audit.modes.base.Mode`-instantie.
        Bij `None` (legacy pad) wordt elk Decision-voorstel direct
        geaccepteerd — equivalent aan AutonoomMode zonder DB-persistentie.
    :param audit_id: Run-scope identifier voor `decisions`/`classifications`.
        Bij `None` wordt er een gegenereerd.
    :param sources: De geselecteerde bronnen voor deze run (default
        `["drive", "miro"]`). Bepaalt zowel de `ingest_scope`-Decision-context
        als de feitelijke ingest: Drive en Miro hebben hun eigen pad; elke
        andere geselecteerde bron (Jira, Planning, …) wordt via het
        `Source`-Protocol ingelezen (`ingest_documenten`). Een bron die niet
        geselecteerd is, wordt niet ingelezen.
    """
    audit_id = audit_id or _maak_audit_id()
    _resume_pending_decisions(audit_id, mode)
    from iso_audit import eigen_output
    from iso_audit.classification.clause_mapping import (
        filter_clause_map,
        koppel_alle_normen,
        laad_clause_map,
        normen_van,
        ontbrekende_dekking,
    )
    from iso_audit.classification.findings import (
        classificeer_alle_bevindingen,
        review_en_bevestig,
        schat_kosten,
    )
    from iso_audit.classification.thema import bepaal_thema
    from iso_audit.config.verbinding import log_veilig
    from iso_audit.miro.ingest import (
        haal_notities_op,
        koppel_aan_clausules,
    )
    from iso_audit.notification import (
        stuur_calendar_uitnodiging,
        stuur_gmail_notificatie,
    )
    from iso_audit.reporting.local_report import schrijf_rapport
    from iso_audit.reporting.report_generation import (
        _genereer_management_summary,
        genereer_rapport,
    )
    from iso_audit.reporting.sheets_gws import sla_op_in_sheets
    from iso_audit.reporting.slide_summary import genereer_slides
    from iso_audit.reporting.tabular_report import schrijf_csv, schrijf_excel
    from iso_audit.sources.drive import haal_documenten_op
    from iso_audit.sources.opvolgpunten import haal_op, levert_opvolgpunten
    from iso_audit.sources.protocol_ingest import ingest_documenten

    logger.info(
        "=== ISO Audit Pipeline gestart (norm: %s, rehash: %s, dry-run-cost: %s) ===",
        norm,
        rehash,
        dry_run_cost,
    )

    logger.info("Stap 1/7: Clausule-map laden...")
    clause_map = laad_clause_map(norm)
    if chapter:
        clause_map = filter_clause_map(clause_map, chapter)
        logger.info("Hoofdstuk-filter actief: alleen clausule %s.*", chapter)

    actieve_bronnen = [s.lower() for s in (sources or ["drive", "miro"])]
    logger.info("Stap 2/7: Documenten inlezen (bronnen: %s)...", ", ".join(actieve_bronnen))
    _emit_decision(
        mode,
        punt="ingest_scope",
        voorstel={"sources": actieve_bronnen, "norm": norm},
        risico="laag",
        context={
            "sources": actieve_bronnen,
            "norm": norm,
            "chapter": chapter,
            # Auditor kan bij integer-modus expliciet om bevestiging vragen:
            "vraag_bevestiging": bool(os.environ.get("ISO_AUDIT_BEVESTIG_SCOPE", "")),
        },
        audit_id=audit_id,
    )
    documenten: list[dict[str, Any]] = []
    handmatige_review: list[dict[str, Any]] = []
    mislukt: dict[str, str] = {}
    if "drive" in actieve_bronnen:
        documenten, handmatige_review = haal_documenten_op(op_dekking=op_dekking)
        if handmatige_review:
            logger.warning(
                "%d bestand(en) vereisen handmatige review: %s",
                len(handmatige_review),
                [h["naam"] for h in handmatige_review],
            )

    # Overige document-bronnen (Jira, Planning, …) via het Source-Protocol.
    # Miro heeft een eigen notitie-pad (stap 3) en valt hierbuiten.
    for bron in actieve_bronnen:
        if bron in ("drive", "miro"):
            continue
        if levert_opvolgpunten(bron):
            # Deze bron levert openstaande punten, geen bewijsmateriaal. Ze gaan buiten
            # de classificatie om rechtstreeks naar de bevindingen — zie stap 5.
            continue
        try:
            extra = ingest_documenten(bron)
            documenten.extend(extra)
            logger.info("Bron %s: %d document(en) ingelezen", bron, len(extra))
        except Exception as e:
            # Doorgaan is juist — één kapotte bron mag een audit niet stilleggen — maar
            # het mag niet stil. Dit stond alleen in het serverlog, waardoor een run
            # `klaar` meldde terwijl een gekozen bron nul documenten leverde. De auditor
            # concludeert dan dat er niets te vinden was.
            _norm = _veilige_reden(e, bron)
            mislukt[bron] = _norm
            log_veilig(
                logger, "Bron %s overgeslagen (ingest-fout, niet kritiek)", bron, exc=e, bron=bron
            )

    logger.info("Stap 3/7: Miro-notities inlezen...")
    miro_notities: list[dict[str, Any]] = []
    if "miro" in actieve_bronnen:
        try:
            miro_notities_raw = haal_notities_op()
            miro_notities = koppel_aan_clausules(miro_notities_raw, clause_map)
            logger.info("%d Miro-notities ingelezen", len(miro_notities))
        except OSError as e:
            log_veilig(logger, "Miro overgeslagen", exc=e, bron="miro")
        except Exception as e:
            log_veilig(logger, "Miro-ingest mislukt (niet kritiek)", exc=e, bron="miro")

    logger.info("Stap 4/7: Documenten koppelen aan clausules...")

    # Eigen output telt niet als bewijs. Gemeten op 2026-08-22: 462 van de 1241 bevindingen
    # (37%) kwamen uit documenten die dit tool zelf schreef — hetzelfde auditrapport in vier
    # formaten, dezelfde bevindingenlijst in twee, en drie eigen memo's. Een bevinding die als
    # bewijs een eerder eigen rapport aanwijst is geen observatie maar een echo, en dat raakt
    # de onafhankelijkheid van de interne auditfunctie.
    #
    # Hier en niet in de bron-adapter: het geldt voor élke bron, en de documenten blijven wél
    # in het landschap staan (zie `_bewaar_ingest` hieronder) zodat navraag mogelijk blijft.
    documenten, eigen_documenten = eigen_output.splits(documenten)
    if eigen_documenten:
        logger.warning(
            "%d document(en) zijn eigen output van dit tool en tellen niet als bewijs: %s",
            len(eigen_documenten),
            [d.get("naam") for d in eigen_documenten][:10],
        )

    cutoff = (date.today() - timedelta(days=2 * 365)).isoformat()
    # Per norm koppelen, niet op een samengevoegde map: `laad_clause_map("beide")` laat 27001
    # de 9001-ingang overschrijven bij een botsend nummer, en dan worden 18 van de 28 ISO
    # 9001-clausules in een gecombineerde audit nooit getoetst.
    maps = {
        n: filter_clause_map(laad_clause_map(n), chapter) if chapter else laad_clause_map(n)
        for n in normen_van(norm)
    }
    gekoppeld_alle, niet_geclassificeerd = koppel_alle_normen(documenten, norm, maps)
    gearchiveerd = [d for d in gekoppeld_alle if (d.get("modified_at") or "") < cutoff]
    gekoppeld = [d for d in gekoppeld_alle if (d.get("modified_at") or "") >= cutoff]
    logger.info(
        "Leeftijdsfilter (%s): %d actief, %d gearchiveerd (>2 jaar oud)",
        cutoff,
        len(gekoppeld),
        len(gearchiveerd),
    )

    # Wat er gelezen is, wordt bewaard — vóór de classificatie en los daarvan.
    #
    # Dit ontbrak: `run_audit` hield alles in het geheugen en schreef pas na stap 5 iets
    # weg. Een run die op de classificatie strandde (bv. een ontbrekende API-key) gooide
    # daarmee een Drive-lezing van tweeënhalve minuut en 149 documenten volledig weg. De
    # losse `ingest.ingest_drive()` deed dit al wél; die twee paden liepen uit elkaar.
    #
    # Los daarvan is het ook wat een auditwerktuig hoort te doen: je hebt bewijs
    # ingezien, dus leg vast wát je hebt ingezien. En het maakt hergebruik mogelijk —
    # zonder opgeslagen documenten valt er niets te cachen.
    # Eigen output gaat wél het landschap in: uitsluiten van bewijs is niet hetzelfde als
    # weggooien, en een auditor mag navragen waarom een document niet is gewogen.
    _bewaar_ingest(gekoppeld_alle + niet_geclassificeerd + eigen_documenten, norm, actieve_bronnen)

    # Openstaande punten gaan buiten de classificatie om: ze zijn al beoordeeld door
    # degene die ze aanmaakte. Daarom ook in alleen-ingest — geen API-key nodig.
    aantal_punten = 0
    for bron in actieve_bronnen:
        if not levert_opvolgpunten(bron):
            continue
        try:
            punten = haal_op(bron, audit_id)
            _bewaar_opvolgpunten(punten, norm)
            aantal_punten += len(punten)
        except Exception as e:
            mislukt[bron] = _veilige_reden(e, bron)
            log_veilig(logger, "Opvolgpunten uit %s overgeslagen", bron, exc=e, bron=bron)

    if alleen_ingest:
        logger.info(
            "Alleen-ingest: %d document(en) en %d openstaand(e) punt(en) vastgelegd, "
            "geen classificatie. Dit pad raakt de Claude-API niet.",
            len(gekoppeld_alle) + len(niet_geclassificeerd),
            aantal_punten,
        )
        # Ná het vastleggen: wat gelezen is blijft bewaard, maar de run meldt niet
        # `klaar` als een gekozen bron niets opleverde.
        if mislukt:
            raise BronIngestError(mislukt)
        return

    if mislukt:
        raise BronIngestError(mislukt)

    ontbrekend = ontbrekende_dekking(gekoppeld, miro_notities, clause_map)

    if niet_geclassificeerd:
        logger.warning(
            "%d document(en) zonder clausule-match: %s",
            len(niet_geclassificeerd),
            [d["naam"] for d in niet_geclassificeerd],
        )

    if dry_run_cost:
        logger.info("Stap 5/7: Kostenschatting (dry-run, GEEN API-calls)...")
        schatting = schat_kosten(
            gekoppeld,
            miro_notities,
            clause_map,
            norm=norm,
            scherpte=scherpte,
            rehash=rehash,
        )
        logger.info("=== Kostenschatting ===")
        for k, v in schatting.items():
            logger.info("  %-25s %s", k + ":", v)
        logger.info("=== Einde dry-run-cost (stoppen voor API-calls) ===")
        return

    logger.info(
        "Stap 5/7: Bevindingen classificeren via Claude... (scherpte=%.1f, rehash=%s)",
        scherpte,
        rehash,
    )
    bevindingen = classificeer_alle_bevindingen(
        gekoppeld,
        miro_notities,
        clause_map,
        norm=norm,
        scherpte=scherpte,
        rehash=rehash,
        op_kosten=op_kosten,
    )

    _auto_triage_voorstellen.clear()
    _autonome_review(
        bevindingen,
        review=review,
        review_steekproef=review_steekproef,
        auto_triage=auto_triage,
    )

    logger.info("Stap 6/7: Menselijke review...")
    bevestigde_bevindingen = review_en_bevestig(bevindingen, auto_accept=no_review)
    bevestigde_bevindingen, _ = _filter_ruis(bevestigde_bevindingen)

    if write_sheets or os.environ.get("AUDIT_SHEETS_ID"):
        sheets_id = sla_op_in_sheets(bevestigde_bevindingen, ontbrekend)
        logger.info("Bevindingen opgeslagen in Sheets: %s", sheets_id)
    else:
        logger.info("Sheets-schrijven overgeslagen (geen AUDIT_SHEETS_ID of --write-sheets).")

    logger.info("Stap 7/7: Rapport en presentatie genereren...")
    try:
        management_summary = _genereer_management_summary(bevestigde_bevindingen)
    except Exception as e:
        logger.warning("Management summary genereren mislukt (%s) — placeholder gebruikt.", e)
        nc = sum(1 for b in bevestigde_bevindingen if b["classificatie"] == "NC")
        ofi = sum(1 for b in bevestigde_bevindingen if b["classificatie"] == "OFI")
        management_summary = (
            f"_(Automatische samenvatting niet beschikbaar: {e})_\n\n"
            f"Bevindingen: {len(bevestigde_bevindingen)} totaal — "
            f"{nc} NC, {ofi} OFI."
        )

    llm_themas: dict[str, str] = {}
    if thema_llm:
        try:
            from iso_audit.classification.thema import verfijn_overig

            llm_themas = verfijn_overig(bevestigde_bevindingen)
        except Exception as e:
            logger.warning("LLM thema-verfijning mislukt (niet kritiek): %s", e)

    for i, bev in enumerate(bevestigde_bevindingen):
        bev_id = str(bev.get("id") or bev.get("_bev_id") or i)
        bev["_bev_id"] = bev_id
        bev["thema"] = llm_themas.get(bev_id) or bepaal_thema(bev)

    lokaal_pad = schrijf_rapport(
        bevestigde_bevindingen,
        ontbrekend,
        handmatige_review,
        management_summary,
        norm,
        gearchiveerd=gearchiveerd,
        scherpte=scherpte,
    )
    logger.info("Lokaal rapport (md): %s", lokaal_pad)

    _converteer_md_naar_html_docx_pdf(lokaal_pad)

    try:
        csv_pad = schrijf_csv(
            bevestigde_bevindingen, norm, scherpte=scherpte, llm_themas=llm_themas
        )
        xlsx_pad = schrijf_excel(
            bevestigde_bevindingen, norm, scherpte=scherpte, llm_themas=llm_themas
        )
        logger.info("Tabulair: %s  |  %s", csv_pad, xlsx_pad)
    except Exception as e:
        logger.warning("Tabulaire export mislukt (niet kritiek): %s", e)

    rapport_doc_id: str | None = None
    slides_id: str | None = None
    if os.environ.get("AUDIT_TEMPLATE_DOC_ID"):
        rapport_doc_id = genereer_rapport(
            bevestigde_bevindingen, ontbrekend, handmatige_review, norm
        )
        slides_id = genereer_slides(bevestigde_bevindingen, norm)
        logger.info("Rapport:     https://docs.google.com/document/d/%s", rapport_doc_id)
        logger.info("Presentatie: https://docs.google.com/presentation/d/%s", slides_id)
    else:
        logger.info("AUDIT_TEMPLATE_DOC_ID niet ingesteld — Google Docs/Slides overgeslagen.")

    if rapport_doc_id and slides_id:
        send_besluit = _emit_decision(
            mode,
            punt="send_report",
            voorstel={
                "verzenden": True,
                "rapport_doc_id": rapport_doc_id,
                "slides_id": slides_id,
                "norm": norm,
                "aantal_bevindingen": len(bevestigde_bevindingen),
            },
            risico="hoog",
            context={
                "nc_count": sum(
                    1 for b in bevestigde_bevindingen if b.get("classificatie") == "NC"
                ),
                "ofi_count": sum(
                    1 for b in bevestigde_bevindingen if b.get("classificatie") == "OFI"
                ),
            },
            audit_id=audit_id,
        )
        if send_besluit.get("verzenden", True):
            stuur_calendar_uitnodiging(rapport_doc_id, slides_id, norm)
            stuur_gmail_notificatie(rapport_doc_id, slides_id, norm, bevestigde_bevindingen)
        else:
            logger.info(
                "send_report-besluit: NIET versturen (reden: %s)",
                send_besluit.get("reden") or send_besluit.get("actie", "auditor"),
            )

    logger.info("=== Audit pipeline klaar ===")


def _converteer_md_naar_html_docx_pdf(md_pad: str) -> None:
    """Keten md → html → docx + pdf; elke stap is best-effort."""
    try:
        from iso_audit.reporting.md_to_html import converteer as md_to_html

        html_pad = md_to_html(md_pad)
        logger.info("HTML: %s", html_pad)
    except Exception as e:
        logger.warning("HTML-conversie mislukt: %s", e)
        return

    try:
        from iso_audit.reporting.html_to_docx import converteer as html_to_docx

        logger.info("DOCX: %s", html_to_docx(html_pad))
    except Exception as e:
        logger.warning("DOCX-conversie mislukt: %s", e)
    try:
        from iso_audit.reporting.html_to_pdf import converteer as html_to_pdf

        logger.info("PDF: %s", html_to_pdf(html_pad))
    except Exception as e:
        logger.warning("PDF-conversie mislukt: %s", e)


AUTO_TRIAGE_ENV = "ISO_AUDIT_AUTO_TRIAGE"

_auto_triage_voorstellen: list[Any] = []
"""Voorstellen uit de laatste run, zodat de aanroeper (het portaal) ze kan toepassen op zijn
eigen werkset. De pipeline kent die werkset niet — hij schrijft in de database, het portaal
beheert `findings.json`."""


def _autonome_review(
    bevindingen: list[dict[str, Any]],
    *,
    review: bool | None,
    review_steekproef: int,
    auto_triage: bool | None = None,
) -> None:
    """Tweede zeef per clausule — alleen als de modus aan staat.

    Deze stap zit **na** de classificatie en **vóór** de menselijke review: hij bereidt het
    oordeel voor dat de auditor daarna neemt. Hij schrijft geen status en raakt de werkset niet;
    zijn uitkomst gaat naar de trail, waar hij per clausule na te lezen is.

    Best-effort zoals de andere niet-essentiële stappen: een mislukte review mag een run die
    verder klopt niet ongeldig maken.
    """
    from iso_audit.classification.review import (
        ReviewInstelling,
        beoordeel,
        groepeer_per_clausule,
    )
    from iso_audit.modellen import review_model

    instelling = ReviewInstelling.bepaal(review)
    if not instelling.aan:
        logger.info("Autonome review staat uit (%s).", instelling.herkomst)
        return

    groepen = groepeer_per_clausule(bevindingen)
    logger.info(
        "Autonome review (%s): %d bevindingen -> %d clausulegroepen, model %s",
        instelling.herkomst,
        len(bevindingen),
        len(groepen),
        review_model(),
    )
    try:
        from iso_audit.store import initialiseer, verbinding

        conn = verbinding()
        initialiseer(conn)
        try:
            uitkomsten = beoordeel(
                groepen,
                instelling=instelling,
                model=review_model(),
                steekproef=review_steekproef,
                conn=conn,
            )
        finally:
            conn.close()
    except Exception as fout:
        logger.warning("Autonome review mislukt (run gaat door): %s", fout)
        return

    from collections import Counter

    adviezen = Counter(a.advies if a else "storing" for _, a, _ in uitkomsten)
    logger.info("Review-adviezen: %s", dict(adviezen))
    _auto_triage(uitkomsten, aan=auto_triage)


def _auto_triage(uitkomsten: list[Any], *, aan: bool | None) -> None:
    """Het onbetwiste deel automatisch afdoen — als die modus aan staat.

    Alleen bevestigde positieve bevindingen. Nooit een NC en nooit een verlaging: dat zijn de
    oordelen waarvoor de auditor-spiegel bestaat. Zie `classification/auto_triage`.

    Aparte schakelaar van de review: je kunt de tweede zeef willen zonder dat er iets
    automatisch wordt afgedaan. Andersom heeft geen zin — zonder review is er geen advies om op
    te varen — dus zonder review gebeurt hier niets.
    """
    from iso_audit.classification.auto_triage import voorstellen
    from iso_audit.classification.review import ReviewInstelling

    instelling = ReviewInstelling.bepaal(aan, env_var=AUTO_TRIAGE_ENV)
    if not instelling.aan:
        logger.info("Auto-triage staat uit (%s).", instelling.herkomst)
        return
    lijst = voorstellen(uitkomsten)
    if not lijst:
        logger.info("Auto-triage: geen enkel voorstel; alles blijft bij de auditor.")
        return
    logger.info(
        "Auto-triage (%s): %d voorstel(len) — pas toe via de werkset van deze audit",
        instelling.herkomst,
        len(lijst),
    )
    _auto_triage_voorstellen.extend(lijst)


def run_report_only(norm: str, scherpte: float = 1.0, thema_llm: bool = False) -> None:
    """Regenereer rapport vanuit bestaande bevindingen-DB. Geen Drive/Miro/classificatie.

    Doel: iteratie op rapport-taal (management summary, OFI-kop, aanbevelingen)
    zonder kosten op de classificatielaag. Gebruikt de bevindingen die al in
    `output/audit_*.db` staan van een eerdere run.
    """
    from iso_audit.classification.clause_mapping import laad_clause_map
    from iso_audit.classification.thema import bepaal_thema
    from iso_audit.reporting.local_report import schrijf_rapport
    from iso_audit.reporting.report_generation import _genereer_management_summary
    from iso_audit.reporting.sheets_gws import sla_op_in_sheets
    from iso_audit.reporting.tabular_report import schrijf_csv, schrijf_excel
    from iso_audit.store import verbinding

    logger.info("=== Report-only: bevindingen herladen uit DB (norm=%s) ===", norm)
    clause_map = laad_clause_map(norm)
    clausules = clause_map.get("clausules", {})

    conn = verbinding()
    rows = conn.execute("SELECT * FROM bevindingen ORDER BY clausule_id").fetchall()
    conn.close()

    if not rows:
        logger.error("Geen bevindingen in DB. Draai eerst de volledige pipeline.")
        sys.exit(1)

    bevindingen: list[dict[str, Any]] = [
        {
            "clausule": r["clausule_id"],
            "clausule_titel": clausules.get(r["clausule_id"], {}).get("titel", r["clausule_id"]),
            "document_naam": r["document_naam"] or "",
            "doc_id": r["doc_id"],
            "herkomst": r["herkomst"],
            "classificatie": r["classificatie"],
            "beschrijving": r["beschrijving"] or "",
            "onderbouwing": r["onderbouwing"] or "",
            "pre_classificatie": r["pre_classificatie"],
        }
        for r in rows
    ]
    logger.info("%d bevindingen geladen uit DB.", len(bevindingen))

    bevindingen, _ = _filter_ruis(bevindingen)

    llm_themas: dict[str, str] = {}
    if thema_llm:
        try:
            from iso_audit.classification.thema import verfijn_overig

            llm_themas = verfijn_overig(bevindingen)
        except Exception as e:
            logger.warning("LLM thema-verfijning mislukt (niet kritiek): %s", e)

    for i, bev in enumerate(bevindingen):
        bev_id = str(bev.get("id") or i)
        bev["_bev_id"] = bev_id
        bev["thema"] = llm_themas.get(bev_id) or bepaal_thema(bev)

    logger.info("Management summary genereren via Claude...")
    try:
        management_summary = _genereer_management_summary(bevindingen)
    except Exception as e:
        logger.error("Management summary mislukt: %s", e)
        sys.exit(1)

    pad = schrijf_rapport(bevindingen, [], [], management_summary, norm, scherpte=scherpte)
    logger.info("Lokaal rapport (md): %s", pad)

    _converteer_md_naar_html_docx_pdf(pad)

    try:
        csv_pad = schrijf_csv(bevindingen, norm, scherpte=scherpte, llm_themas=llm_themas)
        xlsx_pad = schrijf_excel(bevindingen, norm, scherpte=scherpte, llm_themas=llm_themas)
        logger.info("Tabulair: %s  |  %s", csv_pad, xlsx_pad)
    except Exception as e:
        logger.warning("Tabulaire export mislukt (niet kritiek): %s", e)

    if os.environ.get("AUDIT_SHEETS_ID"):
        try:
            sheets_id = sla_op_in_sheets(bevindingen, [])
            logger.info("Sheets gesynchroniseerd: %s", sheets_id)
        except Exception as e:
            logger.warning("Sheets-sync mislukt: %s", e)


def main(argv: list[str] | None = None) -> None:
    """CLI-entrypoint voor de audit pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="ISO Audit Pipeline")
    parser.add_argument(
        "--norm",
        choices=["9001", "27001", "beide"],
        default=os.environ.get("AUDIT_NORM", "beide"),
        help="Toepasselijke norm (default: waarde van AUDIT_NORM in .env)",
    )
    parser.add_argument(
        "--setup-template",
        action="store_true",
        help="Maak het rapporttemplate aan in Drive (eenmalig)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help=("Dry-run met synthetische testdata; geen Drive/Claude/Sheets-verbinding vereist"),
    )
    parser.add_argument(
        "--no-review",
        action="store_true",
        help="Sla interactieve review over en accepteer alle Claude-classificaties",
    )
    parser.add_argument(
        "--write-sheets",
        action="store_true",
        help="Schrijf bevindingen naar Google Sheets (vereist gws auth login)",
    )
    parser.add_argument(
        "--scherpte",
        type=float,
        default=float(os.environ.get("AUDIT_SCHERPTE", "1.0")),
        metavar="0.0-1.0",
        help="Classificatie-scherpte: 1.0=strikt (default), 0.5=genuanceerd (PDCA)",
    )
    parser.add_argument(
        "--chapter",
        default=None,
        metavar="N",
        help="Beperk tot een hoofdstuk (bv. 4, 8, 5.1). Vermindert API-calls sterk.",
    )
    parser.add_argument(
        "--thema-llm",
        action="store_true",
        help=(
            "Verfijn thema-toekenning via LLM voor 'Overig'-findings (route B, enkele Haiku-calls)"
        ),
    )
    parser.add_argument(
        "--rehash",
        action="store_true",
        help=(
            "Ignoreer checkpoint en herclassificeer alle (doc, clausule, norm) combinaties (UPSERT)"
        ),
    )
    parser.add_argument(
        "--dry-run-cost",
        action="store_true",
        help=("Toon alleen kostenschatting van de classificatie-stap — geen API-calls voor LLM"),
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help=("Regenereer rapport vanuit bestaande bevindingen-DB — geen Drive/Miro/classificatie"),
    )
    args = parser.parse_args(argv)

    if args.local_only:
        run_local_only(args.norm)
    elif args.setup_template:
        _valideer_env()
        run_setup_template()
    elif args.report_only:
        run_report_only(args.norm, scherpte=args.scherpte, thema_llm=args.thema_llm)
    else:
        _valideer_env()
        run_audit(
            args.norm,
            no_review=args.no_review,
            write_sheets=args.write_sheets,
            chapter=args.chapter,
            scherpte=args.scherpte,
            thema_llm=args.thema_llm,
            rehash=args.rehash,
            dry_run_cost=args.dry_run_cost,
        )


if __name__ == "__main__":
    main()
