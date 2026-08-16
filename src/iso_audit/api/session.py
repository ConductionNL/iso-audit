"""Auditsessie-state: findings.json + append-only triage-log.

Een sessie is een working-directory met ``findings.json`` (de run-output) en een
``triage_log.jsonl`` (append-only auditor-beslissingen). De render gebeurt via
de bestaande motor (`build_memo`/renderer). Append-only is de auditeerbaarheids-
garantie: reclassificatie/triage wordt nooit overschreven, alleen toegevoegd.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from iso_audit.memo.builder import build_memo
from iso_audit.memo.models import Finding, MemoInput, Severity, TriageStatus
from iso_audit.memo.norm_lookup import laad_norm_db
from iso_audit.memo.renderer.html import MemoRendererImpl
from iso_audit.memo.theme.profile import Profile, laad_profiel


class SessionError(ValueError):
    """Sessie kon niet geladen worden of een actie is ongeldig."""


# Leesbare namen voor de memo-context (scope + geraadpleegde bronnen).
_NORM_NAAM = {"9001": "ISO 9001:2015", "27001": "ISO 27001:2022"}
_BRON_NAAM = {"drive": "Google Drive", "jira": "Jira", "miro": "Miro", "planning": "Planning"}


def _miro_health() -> dict[str, object]:
    """Pseudo-source Miro: gekoppeld zodra het API-token gezet is (READ-only)."""
    import os

    if os.environ.get("MIRO_API_TOKEN"):
        return {"connected": True, "status": "ok", "naam": "miro"}
    # Auditor-taal, geen env-var-naam: het configuratiescherm is niet de plek waar
    # iemand variabelenamen hoort te leren.
    return {
        "connected": False,
        "status": "fail",
        "naam": "miro",
        # Niet `auth`: er is niets geweigerd, er is niets ingevuld. "De credential is
        # geweigerd" sturen bij een leeg veld stuurt iemand naar de leverancier terwijl
        # hij hier één veld moet vullen.
        "soort": "niet_geconfigureerd",
        "reden": "Er is nog geen API-token ingevuld.",
    }


def _check_source(naam: str) -> dict[str, object]:
    """Instantieer één bron-adapter en draai zijn ``healthcheck()``.

    Een exception (geen config, geen auth, netwerk down) betekent: niet
    gekoppeld. We vangen breed — een falende healthcheck mag de UI nooit breken.
    """
    if naam == "miro":
        return _miro_health()
    from iso_audit import sources as source_registry

    try:
        adapter = source_registry.get(naam)()
        # Lichte `probe()` als de adapter die biedt (bv. Drive — anders zou de
        # volledige recursieve healthcheck minuten duren); anders healthcheck().
        check = getattr(adapter, "probe", None) or adapter.healthcheck
        hc = check()
    except Exception as exc:
        # NIET str(exc) doorgeven: die tekst komt uit de client van de leverancier en kan
        # een URL met credential of een tokenfragment bevatten. Tot 2026-08-14 landde dat
        # rechtstreeks in de browser. De ruwe melding gaat nu naar het serverlog.
        from iso_audit.config.verbinding import normaliseer

        soort, tekst = normaliseer(exc, bron=naam)
        return {
            "connected": False,
            "status": "fail",
            "naam": naam,
            "soort": soort,
            "reden": tekst,
        }

    if hc.get("status") == "ok":
        return {"connected": True, **hc}

    # Een adapter die zijn fout zélf afvangt en als `reden` teruggeeft, ging tot
    # 2026-08-14 volledig om de normalisatie heen — en `ui.html` rendert die tekst
    # rechtstreeks. Gemeten was dat onder andere een Jira-401 met tenant-URL en
    # responsbody, en een subprocess-dump met de volledige commandoregel.
    #
    # Daarom hier één uitgang: ontbreekt `soort`, dan is de tekst niet door de
    # normalisatie gegaan en gaat hij er alsnog door. Een adapter die het wél zelf doet
    # (en dus een `soort` meestuurt) blijft ongemoeid. Zo is vergeten niet mogelijk in
    # plaats van "we moeten eraan denken".
    from iso_audit.config.verbinding import normaliseer as _norm

    if not hc.get("soort"):
        soort, tekst = _norm(RuntimeError(str(hc.get("reden", ""))), bron=naam)
        hc = {**hc, "soort": soort, "reden": tekst}
    return {"connected": False, **hc}


def bron_health() -> dict[str, dict[str, object]]:
    """Koppelstatus van alle geregistreerde bronnen, zonder audit.

    Of een bron gekoppeld is, is een eigenschap van de omgeving en niet van één
    audit — daarom module-level en niet op `AuditSession`. Dit is de **enige** bron
    van waarheid voor het configuratiescherm: een tweede, opgeslagen koppel-
    administratie ernaast zou uit de pas gaan lopen, en dan vertelt zij wat iemand
    ooit dacht in plaats van wat het systeem doet.

    Boring & auditable: geen geheime connectiviteitslogica — elke bron rapporteert
    zijn eigen status. Een exception geldt als niet-gekoppeld; een falende
    healthcheck mag de UI nooit breken.
    """
    from iso_audit.ingest import beschikbare_bronnen

    return {naam: _check_source(naam) for naam in beschikbare_bronnen()}


def valideer_bronselectie(gekozen: list[str], *, streng: bool) -> None:
    """Weiger een run die niets zou lezen. Raist `SessionError` met een leesbare reden.

    Tot 2026-08-14 gaf `POST /run/start` `200 {"status": "running"}` op een lege selectie,
    waarna vier gestapelde `or ["drive"]`-terugvallen er stil een drive-run van maakten.
    Voor normen bestond die harde check al (`registry.run_code`); voor bronnen niet.

    `streng` staat aan bij een live-run: dan wordt ook de koppelstatus meegewogen. Bij een
    sim-run niet — die leest per definitie niets, dus een verbindingseis stellen is theater.
    """
    if not gekozen:
        raise SessionError(
            "Kies minstens één bron. Een run zonder bron leest niets en levert geen bevindingen."
        )

    # De adapters registreren zich via side-effect-imports in `beschikbare_bronnen()`.
    # Zonder deze aanroep gooit `sources.get()` een KeyError en lijkt élke bron kapot.
    from iso_audit.ingest import beschikbare_bronnen

    bekend = beschikbare_bronnen()
    onbekend = sorted(set(gekozen) - set(bekend))
    if onbekend:
        raise SessionError(
            f"Onbekende bron(nen): {', '.join(onbekend)}. Beschikbaar: {', '.join(bekend)}."
        )

    if not streng:
        return

    # Alleen de gekozen bronnen controleren, niet `bron_health()` over álle bronnen: dat
    # laatste liet `run/start` op een niet-gekoppelde Jira wachten terwijl de run over
    # Drive ging, en dat kostte meer dan een minuut voordat de run begon.
    health = {n: _check_source(n) for n in gekozen}
    stuk = [n for n in gekozen if not health[n].get("connected")]
    if stuk:
        redenen = "; ".join(f"{n}: {health[n].get('reden', 'niet gekoppeld')}" for n in stuk)
        raise SessionError(
            f"Deze bron(nen) zijn niet gekoppeld, dus een run zou er niets uit lezen: {redenen}"
        )


@dataclass
class _RunState:
    """Voortgang van de stap-2-run (indexatie/timer of live pipeline)."""

    status: str = "idle"
    total: int = 0
    done: int = 0
    start: float = 0.0
    pace: float = 0.0
    mode: str = "sim"
    log: list[str] = field(default_factory=list)


class AuditSession:
    """Bestand-gebaseerde auditsessie (reproduceerbaar, hervatbaar)."""

    def __init__(
        self,
        session_dir: str | Path,
        *,
        profile: str,
        norms_dir: str | Path,
        memo_input_path: str | Path,
    ) -> None:
        self.dir = Path(session_dir)
        self.findings_path = self.dir / "findings.json"
        self.triage_log = self.dir / "triage_log.jsonl"
        if not self.findings_path.is_file():
            raise SessionError(f"Geen findings.json in sessie-dir: {self.dir}")
        self._profile_ref = profile
        self._norms_dir = norms_dir
        self._memo_input_path = Path(memo_input_path)
        self._run = _RunState()
        self.laatste_merge: tuple[int, int] = (0, 0)
        """``(toegevoegd, overgeslagen)`` van de laatste run, zodat een run die dertig
        kandidaten opleverde waarvan achttien al bekend waren niet lijkt alsof hij niets
        deed. De **worker** geeft deze tellingen aan `runs.afsluiten()`; de route deed dat
        eerder, maar die las ze op het moment dat de thread net gestart was en dus altijd
        `(0, 0)`."""

    # --- findings + triage ---------------------------------------------------

    def findings(self) -> list[Finding]:
        data = json.loads(self.findings_path.read_text(encoding="utf-8"))
        return [Finding(**item) for item in data]

    def _save(self, findings: list[Finding]) -> None:
        self.findings_path.write_text(
            json.dumps([f.model_dump() for f in findings], ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def _log(self, entries: list[dict[str, str]]) -> None:
        with self.triage_log.open("a", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    def apply_triage(
        self,
        finding_id: str,
        *,
        severity: Severity | None = None,
        triage_status: TriageStatus | None = None,
        title: str | None = None,
        deviation: str | None = None,
        corrective_measure: str | None = None,
        suggestion: str | None = None,
        reason: str,
        actor: str = "auditor",
        now: datetime | None = None,
    ) -> Finding:
        """Reclassificeer/triage/redigeer één finding; legt elke wijziging append-only vast."""
        findings = self.findings()
        doel = next((f for f in findings if f.id == finding_id), None)
        if doel is None:
            raise SessionError(f"Finding {finding_id!r} niet gevonden.")
        stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
        wijzigingen: list[tuple[str, str, str]] = []

        def _maybe(veld: str, nieuw: str | None) -> None:
            if nieuw is None:
                return
            oud = getattr(doel, veld) or ""
            if nieuw != oud:
                wijzigingen.append((veld, str(oud)[:120], str(nieuw)[:120]))
                setattr(doel, veld, nieuw)

        _maybe("severity", severity)
        _maybe("triage_status", triage_status)
        _maybe("title", title)
        _maybe("deviation", deviation)
        _maybe("corrective_measure", corrective_measure)
        _maybe("suggestion", suggestion)
        if not wijzigingen:
            return doel
        self._save(findings)
        self._log(
            [
                {
                    "timestamp": stamp,
                    "actor": actor,
                    "finding_id": finding_id,
                    "field": veld,
                    "from": oud,
                    "to": nieuw,
                    "reason": reason,
                }
                for veld, oud, nieuw in wijzigingen
            ]
        )
        return doel

    def counts(self) -> dict[str, int]:
        """Tel findings per severity."""
        telling: dict[str, int] = {}
        for f in self.findings():
            telling[f.severity] = telling.get(f.severity, 0) + 1
        return telling

    def config_options(self) -> dict[str, list[str]]:
        """Stap 1: keuzes voor de run — beschikbare normen (norm-DB) en bronnen."""
        from iso_audit.ingest import beschikbare_bronnen

        return {
            "norms": laad_norm_db(self._norms_dir).standards(),
            "sources": beschikbare_bronnen(),
        }

    def source_health(self) -> dict[str, dict[str, object]]:
        """Korte healthcheck per bron — de UI greyt niet-gekoppelde bronnen uit.

        Dunne doorgifte naar :func:`bron_health`; de koppelstatus van een bron is
        geen eigenschap van één audit.
        """
        return bron_health()

    def start_run(
        self,
        *,
        mode: str = "sim",
        norm: str = "9001",
        sources: list[str] | None = None,
        chapter: str | None = None,
        top_n: int = 0,
        pace_s: float = 0.05,
        run_id: str | None = None,
    ) -> dict[str, object]:
        """Stap 2: start de run. ``mode='live'`` = echte pipeline (Drive+LLM);
        ``mode='sim'`` = indexatie-timer (fallback). ``pace_s<=0`` = synchroon (tests).

        `run_id` is het record dat de route al heeft aangelegd; de worker sluit dat af met
        de echte tellingen.
        """
        gekozen = list(sources or [])
        # Inlezen zit niet hier maar op `POST /landschap/ingest`: het documentenlandschap
        # is van de organisatie en niet van één audit, en twee ingangen naar dezelfde
        # opslag laten een auditor geloven dat hij iets eigens heeft.
        valideer_bronselectie(gekozen, streng=(mode == "live"))
        if mode == "live":
            self._run = _RunState(status="running", total=7, start=time.monotonic(), mode="live")
            threading.Thread(
                target=self._run_live_worker,
                args=(norm, gekozen, chapter, top_n, run_id),
                daemon=True,
            ).start()
            return {"mode": "live", "status": "running"}

        total = len(self.findings())
        self._run = _RunState(
            status="running", total=total, start=time.monotonic(), pace=pace_s, mode="sim"
        )
        if pace_s <= 0:
            self._run.done = total
            self._run.status = "done"
        else:
            threading.Thread(target=self._run_worker, args=(run_id,), daemon=True).start()
        return {"mode": "sim", "total": total, "status": self._run.status}

    def _run_worker(self, run_id: str | None = None) -> None:
        from iso_audit.api.runs import afsluiten

        run = self._run
        for i in range(run.total):
            time.sleep(run.pace)
            run.done = i + 1
        run.status = "done"
        # Ook een sim-run moet zijn record afsluiten, anders blijft hij eeuwig "loopt".
        if run_id:
            afsluiten(self.dir, run_id)

    def _run_live_worker(
        self,
        norm: str,
        sources: list[str],
        chapter: str | None,
        top_n: int,
        run_id: str | None = None,
    ) -> None:
        from iso_audit.api.run_job import draft_from_db, run_live_pipeline
        from iso_audit.api.runs import afsluiten

        def _on_log(msg: str) -> None:
            self._run.log.append(msg)
            m = re.search(r"Stap (\d+)/(\d+)", msg)
            if m:
                self._run.done, self._run.total = int(m.group(1)), int(m.group(2))

        try:
            run_live_pipeline(
                norm=norm,
                sources=sources,
                chapter=chapter,
                on_log=_on_log,
            )
            self._run.log.append("Findings exporteren + kop-NC's draften…")
            drafted = draft_from_db(
                norm=norm, norms_dir=str(self._norms_dir), language="nl", top_n=top_n
            )
            # AANVULLEN, niet overschrijven. Eerder deed dit `self._save(drafted)` en
            # daarmee gooide een tweede run alle triage van de eerste weg — precies
            # wat de spec `audit-registry` verbiedt. De dedup zit in `api.runs`;
            # overgeslagen duplicaten worden door de route bij het run-record geteld.
            from iso_audit.api.runs import voeg_toe

            self.laatste_merge = voeg_toe(self.dir, [f.model_dump() for f in drafted])
            # De memo-context bijwerken is cosmetiek ná het echte werk: de bevindingen
            # staan op dit punt al in `findings.json`. Op 2026-08-16 liet een ontbrekende
            # `memo-input.yaml` een run die alle zeven stappen én alle rapporten had
            # afgerond, alsnog als `fout` met `0 toegevoegd` in de trail belanden. Het
            # spoor moet vertellen wat er gebeurd is; een cosmetische stap mag dat niet
            # omkeren. Wel gelogd, want stil is het ook niet.
            try:
                self._update_memo_context(norm, sources, chapter)
            except Exception as exc:
                self._run.log.append(f"Memo-context niet bijgewerkt: {exc}")
            self._run.done = self._run.total
            self._run.status = "done"
            # Hier, en niet in de route: de uitkomst is van de worker. De route kende bij
            # het starten alleen `(0, 0)`.
            if run_id:
                toegevoegd, overgeslagen = self.laatste_merge
                afsluiten(self.dir, run_id, toegevoegd=toegevoegd, overgeslagen=overgeslagen)
        except Exception as exc:  # surface elke pipeline-fout in de UI
            self._run.log.append(f"FOUT: {exc}")
            self._run.status = "error"
            if run_id:
                afsluiten(self.dir, run_id, fout=str(exc))

    def run_progress(self) -> dict[str, object]:
        """Voortgang van stap 2: done/total, verstreken tijd, ETA en (live) logregels."""
        r = self._run
        elapsed = (time.monotonic() - r.start) if r.status != "idle" else 0.0
        eta = (r.total - r.done) * (elapsed / r.done) if r.done and r.status == "running" else 0.0
        return {
            "status": r.status,
            "mode": r.mode,
            "total": r.total,
            "done": r.done,
            "elapsed_s": round(elapsed, 1),
            "eta_s": round(eta, 1),
            "log": r.log[-25:],
        }

    def run_summary(
        self, *, norms: list[str] | None = None, sources: list[str] | None = None
    ) -> dict[str, object]:
        """Stap 2: voer (of toon) de run o.b.v. de gekozen config."""
        return {
            "config": {"norms": norms or [], "sources": sources or []},
            "findings": len(self.findings()),
            "counts": self.counts(),
            "note": (
                "Findings uit de sessie (resultaat van een eerdere run). Live ingest "
                "via de gekozen bron(nen) is de connector-orchestration-fase."
            ),
        }

    def finding_context(self, finding_id: str) -> dict[str, object]:
        """Hover-context: de échte normtekst per clausule + waarom NC-kandidaat."""
        doel = next((f for f in self.findings() if f.id == finding_id), None)
        if doel is None:
            raise SessionError(f"Finding {finding_id!r} niet gevonden.")
        db = laad_norm_db(self._norms_dir)
        lang = self._profile().defaults.language
        citations: list[dict[str, str]] = []
        for clause in [doel.clause, *doel.extra_clauses]:
            try:
                citations.append(db.citation(doel.standard, clause, lang).model_dump())
            except Exception:  # ontbrekende clausule mag de hover niet breken
                continue
        return {
            "citations": citations,
            "reasoning": doel.reasoning,
            "deviation": doel.deviation or doel.description,
            "verify_with": doel.verify_with or "",
            "bronnen": [b.model_dump() for b in doel.bronnen],
            "thema": doel.thema or "",
            "examples": doel.examples,
            # Redigeerbaar in de triage-uitklap: NC → maatregel, OFI → aanbeveling.
            "severity": doel.severity,
            "corrective_measure": doel.corrective_measure or "",
            "suggestion": doel.suggestion or "",
        }

    def conclusion(self) -> dict[str, object]:
        """Saturatie-conclusie na triage: telling + advies (auditor beslist)."""
        nc = [f for f in self.findings() if f.severity == "NC"]
        tally = {
            s: sum(1 for f in nc if f.triage_status == s)
            for s in ("open", "valide", "niet_valide", "follow_up")
        }
        open_n, follow = tally["open"], tally["follow_up"]
        if open_n:
            advies = f"{open_n} kandidaat-NC('s) nog niet beoordeeld."
        elif follow:
            advies = f"{follow} follow-up('s) open — meer audits nodig voor saturatie."
        else:
            advies = "Voldoende saturatie — de MT-memo kan opgesteld worden."
        return {
            "tally": tally,
            "all_triaged": open_n == 0,
            "saturated": open_n == 0 and follow == 0,
            "advice": advies,
            "ofi_themes": self._ofi_themes(),
        }

    def _ofi_themes(self) -> list[dict[str, object]]:
        """OFI's gegroepeerd per thema (aflopend) — verbeter-thematisering.

        Het idee: aan een thema met veel OFI's werken tilt de organisatie breed
        op. Levert per thema het aantal OFI's + de betrokken clausules.
        """
        counts: dict[str, int] = {}
        clauses: dict[str, set[str]] = {}
        for f in self.findings():
            if f.severity != "OFI":
                continue
            thema = f.thema or "Overig"
            counts[thema] = counts.get(thema, 0) + 1
            clauses.setdefault(thema, set()).add(f.clause)
        geordend = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
        return [{"thema": t, "count": n, "clauses": sorted(clauses[t])} for t, n in geordend]

    def triage_summary(self) -> dict[str, object]:
        """Triage-voortgang: een memo mag pas bij 0 openstaande NC-kandidaten."""
        nc = [f for f in self.findings() if f.severity == "NC"]
        open_n = sum(1 for f in nc if f.triage_status == "open")
        return {"total_nc": len(nc), "open": open_n, "complete": open_n == 0}

    def trail(self) -> list[dict[str, str]]:
        """De append-only triage-trail (chronologisch)."""
        if not self.triage_log.is_file():
            return []
        return [
            json.loads(regel)
            for regel in self.triage_log.read_text(encoding="utf-8").splitlines()
            if regel.strip()
        ]

    # --- render --------------------------------------------------------------

    def _profile(self) -> Profile:
        return laad_profiel(self._profile_ref)

    def render_html(self) -> str:
        mi = MemoInput(**(yaml.safe_load(self._memo_input_path.read_text("utf-8")) or {}))
        memo = build_memo(
            findings=self.findings(),
            historical_ncs=[],
            profile=self._profile(),
            norm_db=laad_norm_db(self._norms_dir),
            memo_input=mi,
        )
        return MemoRendererImpl().render_html(memo, self._profile())

    def export_pdf(self, output: str | Path) -> Path:
        pad = Path(output)
        MemoRendererImpl().render_pdf(self.render_html(), pad)
        return pad

    # --- memo-input (bewerkbaar vóór generatie) ------------------------------

    def memo_input_data(self) -> dict[str, object]:
        """De bewerkbare memo-koptekst + context (voor de pre-generatie editor)."""
        data: dict[str, object] = yaml.safe_load(self._memo_input_path.read_text("utf-8")) or {}
        return data

    def update_memo_input(self, data: dict[str, object]) -> dict[str, object]:
        """Valideer + schrijf de memo-input — auditor past de memo aan vóór generatie.

        Validatie via het MemoInput-model; een ongeldige structuur faalt hier
        (→ 400 in de API) i.p.v. pas bij de render.
        """
        mi = MemoInput.model_validate(data)
        self._memo_input_path.write_text(
            yaml.safe_dump(mi.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return mi.model_dump()

    def _update_memo_context(self, norm: str, sources: list[str], chapter: str | None) -> None:
        """Na een live run: scope (norm + hoofdstuk) en geraadpleegde bronnen in
        de memo-context zetten — de geselecteerde bronnen (Drive/Jira/…), niet de
        DB/dataset. De auditor kan dit daarna nog aanpassen via de memo-editor.
        """
        data = self.memo_input_data()
        ctx = data.setdefault("context", {})
        if not isinstance(ctx, dict):
            return
        norms = ["9001", "27001"] if norm == "beide" else [norm]
        bereik = f"§{chapter}" if chapter else "§4 t/m §10"
        ctx["scope"] = {_NORM_NAAM.get(n, n): bereik for n in norms}
        ctx["sources"] = [_BRON_NAAM.get(s, s) for s in (sources or ["drive"])]
        self._memo_input_path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
