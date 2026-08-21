"""Planning-source — auditplanning uit Google Sheets als `Source`-adapter.

Leest een auditplanning Spreadsheet met meerdere tabs (jaar x norm), parseert
de maandkolommen en yields elke geconfigureerde clausule-row als `Document`
(`type="audit-planning"`). De legacy `run()`-functie blijft beschikbaar om
de pipeline-DB-tabel `audit_planning` te vullen.

Gemigreerd uit `Ops_to_Biz/audit/planning_ingest.py` + `audit/gsa_client.py`
per milestone B §2.3.5-§2.3.7. Sheets-API gaat via
`iso_audit.clients.google_sheets.sheets_lees_alle_tabs`, met het
org-service-account uit `iso_audit.auth` — consistent met DriveSource, en zonder
de persoonsgebonden `gws`-CLI-sessie die hier eerder stond.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from dotenv import load_dotenv

from iso_audit.clients.google_sheets import sheets_lees_alle_tabs, sheets_tabnamen
from iso_audit.config.google_ids import uit_url
from iso_audit.config.verbinding import normaliseer
from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding

load_dotenv()
logger = logging.getLogger(__name__)

PLANNING_SHEETS_ID_ENV = "AUDIT_PLANNING_SHEETS_ID"

# Bewust géén DEFAULT_PLANNING_SHEETS_ID. Tot 2026-08-16 stond hier het
# spreadsheet-ID van Conduction als terugval. Gemeten in het cluster op die datum:
# noch `AUDIT_SOURCE_FOLDER_ID` noch `AUDIT_PLANNING_SHEETS_ID` was gezet, waarop
# Drive zich (terecht) als niet-gekoppeld meldde maar planning **groen** met 7 tabs —
# op andermans spreadsheet. Bij een derde partij wijst het portaal dan groen naar
# data van Conduction. Een lege configuratie hoort zichtbaar leeg te zijn.


def _valideer_sheet_id(sid: str) -> str:
    """Normaliseer een geplakte Sheets-URL naar het ID, en waarschuw bij misvorming.

    Een Google Sheets-ID bestaat uit ``[A-Za-z0-9_-]``. Een ``=`` of whitespace
    duidt bijna altijd op een .env-fout — bv. een regel zonder newline die de
    volgende toewijzing aan de waarde plakt (``...37AGOOGLE_SERVICE_ACCOUNT_FILE=
    ...``). We loggen dan een duidelijke waarschuwing i.p.v. verderop een
    cryptische API-fout te krijgen. In dát geval wordt de waarde NIET aangepast:
    stilletjes een andere sheet aanspreken is erger dan zichtbaar falen.

    Een volledige Sheets-URL is een ander geval en wordt wél herleid. Dat spreekt
    geen andere sheet aan maar exact degene die in de URL staat, en het is wat
    iedereen uit de adresbalk kopieert — gemeten op 2026-08-14, zowel via de UI als
    uit een omgevingsbestand. Zonder herleiding krijgt de API een "ID" van 80 tekens
    en antwoordt met 404, wat in het portaal verschijnt als "niet gedeeld met dit
    account" en dus naar het verkeerde probleem wijst.
    """
    sid = uit_url(sid)
    if "=" in sid or any(c.isspace() for c in sid):
        logger.warning(
            "%s lijkt misvormd: bevat '=' of whitespace (%d tekens). Waarschijnlijk "
            "een .env-regel zonder newline. Verwacht alleen [A-Za-z0-9_-]. "
            "Controleer je .env.",
            PLANNING_SHEETS_ID_ENV,
            len(sid),
        )
    return sid


def _resolve_spreadsheet_id(expliciet: str | None = None) -> str:
    """Bepaal het planning-spreadsheet-ID; lege string als er niets geconfigureerd is.

    Geen terugval op een ingebakken ID — zie de opmerking bovenaan. Niet-geconfigureerd
    is een geldige toestand die `probe()`/`healthcheck()` als zodanig melden; wie er
    écht mee wil lezen krijgt een harde fout via `_vereis_id`.
    """
    waarde = expliciet or os.environ.get(PLANNING_SHEETS_ID_ENV) or ""
    return _valideer_sheet_id(waarde) if waarde else ""


def _vereis_id(sid: str) -> str:
    """Geef het ID terug, of raise als de planning niet gekoppeld is.

    Lezen zonder configuratie hoort te falen, niet stilletjes iets anders te lezen.
    """
    if not sid:
        raise OSError(
            f"Geen planning-spreadsheet geconfigureerd. Stel {PLANNING_SHEETS_ID_ENV} in, "
            "of vul het Spreadsheet-ID in bij Configuratie → Auditplanning."
        )
    return sid


MAANDEN: tuple[str, ...] = (
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
)


def _norm_uit_tabnaam(tab_naam: str) -> str:
    """Lees ISO-norm uit tabnaam: `9001`, `27001` of `beide` (fallback)."""
    lower = tab_naam.lower()
    if "27001" in lower:
        return "27001"
    if "9001" in lower:
        return "9001"
    return "beide"


def _jaar_uit_tabnaam(tab_naam: str) -> int | None:
    """Laatste 4-cijferig jaar (`20\\d\\d`) uit de tabnaam, of `None`."""
    treffers = re.findall(r"20\d{2}", tab_naam)
    return int(treffers[-1]) if treffers else None


def _normaliseer_clausule(raw: str) -> str | None:
    """Normaliseer clausule-ID naar `X.Y` (eerste twee componenten)."""
    m = re.match(r"(\d+\.\d+)", str(raw).strip())
    return m.group(1) if m else None


def _detecteer_maandkolommen(rijen: list[list[Any]]) -> tuple[int, dict[int, str]]:
    """Vind de header-rij met maandnamen en bouw `{col_index: maand_naam}`.

    Returnt `(-1, {})` als geen maand-rij is gevonden.
    """
    for i, rij in enumerate(rijen):
        cellen = [str(c).strip().lower() for c in rij]
        if any(m in cellen for m in MAANDEN):
            maand_cols = {
                j: str(rij[j]).strip().lower() for j, c in enumerate(cellen) if c in MAANDEN
            }
            return i, maand_cols
    return -1, {}


@dataclass(frozen=True, slots=True)
class _PlanningRow:
    """Eén planning-regel: clausule + norm + jaar + geplande maanden."""

    clausule_id: str
    norm: str
    jaar: int | None
    gepland_maanden: list[str]
    notitie: str
    bron_tab: str

    @property
    def status(self) -> str:
        return "gepland" if self.gepland_maanden else "open"

    @property
    def kwartaal(self) -> str:
        return ", ".join(self.gepland_maanden)


def _cel(rij: list[Any], idx: int) -> str:
    """Veilige cell-access — geef lege string bij out-of-range."""
    if idx >= len(rij):
        return ""
    return str(rij[idx]).strip()


def _parse_tab(tab_naam: str, rijen: list[list[Any]]) -> list[_PlanningRow]:
    """Parse één planning-tab tot een lijst `_PlanningRow`."""
    if not rijen or len(rijen) < 2:
        logger.info("Tab '%s': leeg of alleen header — overgeslagen", tab_naam)
        return []
    norm = _norm_uit_tabnaam(tab_naam)
    jaar = _jaar_uit_tabnaam(tab_naam)
    maand_idx, maand_cols = _detecteer_maandkolommen(rijen)
    if not maand_cols:
        logger.warning("Tab '%s': geen maandkolommen gevonden — tab overgeslagen", tab_naam)
        return []

    out: list[_PlanningRow] = []
    for rij in rijen[maand_idx + 1 :]:
        if not rij:
            continue
        clausule_raw = _cel(rij, 1)
        clausule_id = _normaliseer_clausule(clausule_raw)
        if not clausule_id:
            continue
        notitie = _cel(rij, 4)
        gepland_maanden = [
            maand_cols[j] for j in maand_cols if j < len(rij) and str(rij[j]).strip().lower() == "x"
        ]
        out.append(
            _PlanningRow(
                clausule_id=clausule_id,
                norm=norm,
                jaar=jaar,
                gepland_maanden=gepland_maanden,
                notitie=notitie,
                bron_tab=tab_naam,
            )
        )
    return out


def _initialiseer_planning_tabel(conn: sqlite3.Connection) -> None:
    """Maak `audit_planning`-tabel aan als die nog niet bestaat."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_planning (
            clausule_id   TEXT NOT NULL,
            norm          TEXT NOT NULL,
            jaar          INTEGER,
            kwartaal      TEXT,
            eigenaar      TEXT,
            status        TEXT,
            notitie       TEXT,
            bron_tab      TEXT,
            bijgewerkt_op TEXT NOT NULL,
            PRIMARY KEY (clausule_id, norm, jaar)
        )
        """
    )
    conn.commit()


@register
class PlanningSource:
    """Google Sheets-based audit-planning-adapter (`Source` Protocol)."""

    naam = "planning"

    def __init__(self, spreadsheet_id: str | None = None) -> None:
        self._spreadsheet_id = _resolve_spreadsheet_id(spreadsheet_id)
        # Momentopname van de planning voor deze instantie; zie `_fetch_alle`. Op de
        # instantie en niet op de klasse: klasse-state lekt tussen runs en tussen tests.
        self._rijen: list[_PlanningRow] | None = None

    @property
    def spreadsheet_id(self) -> str:
        return self._spreadsheet_id

    def _fetch_alle(self) -> list[_PlanningRow]:
        """Lees alle tabs en parse elke tab tot planning-rows; één keer per instantie.

        De cache is geen optimalisatie maar een reparatie. `protocol_ingest` roept
        `fetch_content()` **per document** aan, en die riep dit opnieuw aan — dus per
        planning-rij één `spreadsheets.get` plus één `values.get` per tab. Bij ~200 rijen en
        ~15 tabs zijn dat duizenden Sheets-calls in één run, ruim boven het leesquotum per
        minuut. Gemeten in de productierun van 2026-08-21: tientallen
        `HttpError 429`-waarschuwingen en tabs die daardoor werden overgeslagen, dus een
        planning die half werd gelezen zonder dat het rapport dat zei.

        Cachen op de instantie en niet module-breed: een Source leest zijn configuratie bij
        constructie en is daarmee de natuurlijke levensduur van deze momentopname. Een
        volgende run bouwt een nieuwe instantie en leest opnieuw.
        """
        if self._rijen is None:
            tabs = sheets_lees_alle_tabs(_vereis_id(self._spreadsheet_id))
            alle: list[_PlanningRow] = []
            for tab_naam, rijen in tabs.items():
                alle.extend(_parse_tab(tab_naam, rijen))
            self._rijen = alle
        return self._rijen

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        """Yield één Document per planning-rij in de bron-spreadsheet.

        `filter` wordt nu nog niet ondersteund; toekomstige uitbreiding kan
        bv. `{"norm": "9001"}` of `{"jaar": 2026}` accepteren.
        """
        del filter
        for row in self._fetch_alle():
            yield Document(
                id=f"{row.norm}:{row.clausule_id}:{row.jaar}",
                titel=f"Planning {row.norm} §{row.clausule_id} ({row.jaar})",
                bron=self.naam,
                type="audit-planning",
                laatst_gewijzigd="",
                inhoud_uri=row.bron_tab,
            )

    def fetch_content(self, doc: Document) -> str:
        """Geef de notitie + geplande maanden terug als plain text."""
        if doc.bron != self.naam:
            raise ValueError(
                f"PlanningSource krijgt document uit bron={doc.bron!r}, verwacht {self.naam!r}"
            )
        # Resolutie via doc.id (norm:clausule:jaar).
        try:
            norm, clausule_id, jaar_s = doc.id.split(":")
            jaar: int | None = int(jaar_s) if jaar_s != "None" else None
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalide PlanningSource doc.id: {doc.id!r}") from e
        for row in self._fetch_alle():
            if row.norm == norm and row.clausule_id == clausule_id and row.jaar == jaar:
                gepland = row.kwartaal or "(geen gepland)"
                return f"Status: {row.status}\nGepland: {gepland}\nNotitie: {row.notitie}"
        return ""

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        """Planning levert geen findings — lege iterator."""
        del sessie_id
        return iter([])

    def _niet_gekoppeld(self) -> dict[str, object]:
        """Status voor "er is geen spreadsheet ingevuld" — geen leveranciersfout.

        Eigen tekst, dus die mag letterlijk door (zie `config/verbinding.py`). In
        auditor-taal: het configuratiescherm is niet de plek om env-var-namen te leren.
        """
        return {
            "status": "fail",
            "naam": self.naam,
            "tenant": "",
            "soort": "niet_geconfigureerd",
            "reden": "Nog niet ingevuld: het spreadsheet-ID van de auditplanning.",
        }

    def probe(self) -> dict[str, object]:
        """Lichte connectiviteits-probe: alleen de tabtitels opvragen.

        `healthcheck()` leest álle tabs volledig, en die werd bij élke keer openen van het
        configuratiescherm aangeroepen. Eén metadata-call bewijst hetzelfde: de credential
        werkt en de spreadsheet is bereikbaar.
        """
        if not self._spreadsheet_id:
            return self._niet_gekoppeld()
        try:
            namen = sheets_tabnamen(self._spreadsheet_id)
        except Exception as e:
            soort, tekst = normaliseer(e, bron=self.naam)
            return {
                "status": "fail",
                "naam": self.naam,
                "tenant": self._spreadsheet_id,
                "soort": soort,
                "reden": tekst,
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "tenant": self._spreadsheet_id,
            "aantal_tabs": len(namen),
        }

    def healthcheck(self) -> dict[str, object]:
        """Verifieer dat de planning-spreadsheet bereikbaar is (leest alle tabs)."""
        if not self._spreadsheet_id:
            return self._niet_gekoppeld()
        try:
            tabs = sheets_lees_alle_tabs(self._spreadsheet_id)
        except Exception as e:
            soort, tekst = normaliseer(e, bron=self.naam)
            return {
                "status": "fail",
                "naam": self.naam,
                "tenant": self._spreadsheet_id,
                "soort": soort,
                "reden": tekst,
            }
        return {
            "status": "ok",
            "naam": self.naam,
            "tenant": self._spreadsheet_id,
            "aantal_tabs": len(tabs),
        }


# ---------------------------------------------------------------------------
# Legacy CLI — vult `audit_planning`-tabel in de lokale audit-DB
# ---------------------------------------------------------------------------


def run(droog: bool = False, spreadsheet_id: str | None = None) -> None:
    """Lees planning-spreadsheet en UPSERT alle rijen in `audit_planning`.

    Bij `droog=True` wordt alleen geprint, geen DB-mutatie. Vereist dat de
    `iso_audit.store` DB-paden geconfigureerd zijn.
    """
    from iso_audit.store import initialiseer, verbinding

    conn = verbinding()
    initialiseer(conn)
    _initialiseer_planning_tabel(conn)

    sid = _vereis_id(_resolve_spreadsheet_id(spreadsheet_id))
    logger.info("Auditplanning inlezen uit Sheets: %s", sid)
    tabs = sheets_lees_alle_tabs(sid)
    if not tabs:
        logger.error("Geen tabs gevonden — controleer auth en spreadsheet-ID")
        conn.close()
        return

    nu = datetime.now(UTC).isoformat()
    totaal = 0
    for tab_naam, rijen in tabs.items():
        rows = _parse_tab(tab_naam, rijen)
        for row in rows:
            if droog:
                print(
                    f"  [{tab_naam}] {row.clausule_id} | {row.norm} | "
                    f"{row.jaar} | gepland={row.gepland_maanden} | "
                    f"{row.notitie[:40]}"
                )
            else:
                conn.execute(
                    """
                    INSERT INTO audit_planning
                        (clausule_id, norm, jaar, kwartaal, eigenaar, status,
                         notitie, bron_tab, bijgewerkt_op)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(clausule_id, norm, jaar) DO UPDATE SET
                        kwartaal      = excluded.kwartaal,
                        eigenaar      = excluded.eigenaar,
                        status        = excluded.status,
                        notitie       = excluded.notitie,
                        bron_tab      = excluded.bron_tab,
                        bijgewerkt_op = excluded.bijgewerkt_op
                    """,
                    (
                        row.clausule_id,
                        row.norm,
                        row.jaar,
                        row.kwartaal,
                        "",
                        row.status,
                        row.notitie,
                        row.bron_tab,
                        nu,
                    ),
                )
            totaal += 1
        logger.info("Tab '%s': %d planningregels verwerkt", tab_naam, len(rows))

    if not droog:
        conn.commit()
    conn.close()
    actie = "gevonden (dry-run)" if droog else "opgeslagen in DB"
    logger.info("Klaar: %d planningregels %s", totaal, actie)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(description="Auditplanning inlezen uit Google Sheets")
    parser.add_argument(
        "--droog",
        action="store_true",
        help="Dry-run — print regels, schrijf niets",
    )
    args = parser.parse_args()
    run(droog=args.droog)
    return 0
