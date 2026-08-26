"""Typer-CLI: ``iso-audit memo`` + ``iso-audit profile``.

Dunne schil boven builder/renderer/profile-loader. Boring & auditable: expliciete
paden, heldere fouten, geen stille fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn

import typer
import yaml
from rich.console import Console

from iso_audit.memo.builder import THEMA_DREMPEL, build_memo
from iso_audit.memo.models import Finding, HistoricalNC, MemoInput
from iso_audit.memo.norm_lookup import laad_norm_db
from iso_audit.memo.renderer.html import MemoRendererImpl
from iso_audit.memo.theme.profile import ProfileError, laad_profiel

app = typer.Typer(help="Auditmemo-generatie en profielbeheer.", no_args_is_help=True)
profile_app = typer.Typer(
    help="Profielbeheer (branding/auditor/standaarden).", no_args_is_help=True
)
app.add_typer(profile_app, name="profile")
_console = Console()


def _fail(msg: str) -> NoReturn:
    _console.print(f"[red]fout:[/red] {msg}")
    raise typer.Exit(code=1)


def _laad_findings(pad: Path) -> list[Finding]:
    data = json.loads(pad.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        _fail(f"{pad}: verwacht een JSON-lijst van findings.")
    return [Finding(**item) for item in data]


def _laad_yaml_lijst(pad: Path, key: str) -> list[dict[str, Any]]:
    data = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
    entries = data.get(key, [])
    if not isinstance(entries, list):
        _fail(f"{pad}: '{key}' moet een lijst zijn.")
    return list(entries)


@app.command("memo")
def memo_cmd(
    profile: str = typer.Option(..., "--profile", help="Profiel-slug of pad."),
    findings: Path = typer.Option(..., "--findings", help="Findings-dataset (JSON)."),
    memo_input: Path = typer.Option(..., "--memo-input", help="Memo-koptekst + context (YAML)."),
    norms: Path = typer.Option(..., "--norms", help="Directory met norm-DB <slug>.yaml."),
    output: Path = typer.Option(..., "--output", help="Output-basispad (zonder extensie)."),
    historical_ncs: Path | None = typer.Option(
        None, "--historical-ncs", help="Historical-NCs (YAML)."
    ),
    language: str | None = typer.Option(None, "--language", help="Taal (default: profiel)."),
    threshold: int = typer.Option(
        THEMA_DREMPEL, "--threshold", help="Aantal OFI's op één thema voor een verbeterpunt."
    ),
) -> None:
    """Genereer de management-auditmemo (HTML + PDF) uit de findings-dataset."""
    try:
        prof = laad_profiel(profile)
        norm_db = laad_norm_db(norms)
        finding_list = _laad_findings(findings)
        mi = MemoInput(**(yaml.safe_load(memo_input.read_text(encoding="utf-8")) or {}))
        hist = (
            [HistoricalNC(**e) for e in _laad_yaml_lijst(historical_ncs, "entries")]
            if historical_ncs
            else []
        )
        memo = build_memo(
            findings=finding_list,
            historical_ncs=hist,
            profile=prof,
            norm_db=norm_db,
            memo_input=mi,
            language=language,
            threshold=threshold,
        )
        renderer = MemoRendererImpl()
        html = renderer.render_html(memo, prof)
    except (ProfileError, ValueError, OSError) as exc:
        _fail(str(exc))

    html_pad = output.with_suffix(".html")
    html_pad.parent.mkdir(parents=True, exist_ok=True)
    html_pad.write_text(html, encoding="utf-8")
    pdf_pad = output.with_suffix(".pdf")
    budget = renderer.render_pdf(html, pdf_pad)
    _console.print(f"[green]memo geschreven:[/green] {html_pad} + {pdf_pad}")
    # Het paginabudget hoort in beeld bij degene die de memo maakt, niet alleen in een logregel.
    # De klanteis is één tot drie A4; stil overschrijden breekt hem zonder dat iemand het ziet.
    if budget.past:
        _console.print(f"[green]{budget.paginas} pagina('s)[/green] — binnen de eis")
    else:
        _console.print(f"[yellow]{budget.melding}[/yellow]")


@app.command("draft")
def draft_cmd(
    findings: Path = typer.Option(..., "--findings", help="Ruwe findings-dataset (JSON)."),
    norms: Path = typer.Option(..., "--norms", help="Directory met norm-DB <slug>.yaml."),
    output: Path = typer.Option(..., "--output", help="Pad voor de draft findings-JSON."),
    top_n: int = typer.Option(0, "--top-n", help="Aantal kop-NC's (0 = alle kandidaten)."),
    language: str = typer.Option("nl", "--language", help="Taal voor de draft."),
) -> None:
    """Draft (via LLM) de top-NC's uit een ruwe run → bewerkbare findings-JSON.

    De auditor redigeert de output en draait daarna `iso-audit memo`.
    """
    from iso_audit.memo.draft import draft_findings

    try:
        norm_db = laad_norm_db(norms)
        ruw = _laad_findings(findings)
        gedraft = draft_findings(ruw, norm_db=norm_db, language=language, top_n=top_n)
    except (ValueError, OSError) as exc:
        _fail(str(exc))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([f.model_dump() for f in gedraft], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    n_nc = sum(1 for f in gedraft if f.severity == "NC")
    _console.print(
        f"[green]draft geschreven:[/green] {output} ({n_nc} kop-NC's). "
        "Redigeer titel/afwijking/maatregel/acties en draai daarna `iso-audit memo --findings <dit-bestand>`."
    )


@app.command("ui")
def ui_cmd(
    audits: Path = typer.Option(
        ..., "--audits", help="Root-directory met de audits (elke audit een submap)."
    ),
    profile: str = typer.Option(..., "--profile", help="Profiel-slug of pad."),
    norms: Path = typer.Option(..., "--norms", help="Directory met norm-DB <slug>.yaml."),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind-host (lokaal-only default)."),
    port: int = typer.Option(8000, "--port", help="Poort."),
) -> None:
    """Start het auditorportaal: dashboard, triage en memo.

    Twee vlaggen zijn gewijzigd door change `portal-dashboard`: `--session` is
    `--audits` geworden omdat het portaal nu meerdere audits kent, en
    `--memo-input` is vervallen — de memo-input hoort bij één audit en staat in de
    audit-directory, niet in een globale vlag.
    """
    from iso_audit.api.app import serve

    _console.print(f"[green]auditorportaal op[/green] http://{host}:{port}  (Ctrl-C om te stoppen)")
    serve(audits, profile=profile, norms_dir=norms, host=host, port=port)


@profile_app.command("new")
def profile_new(
    overschrijf: bool = typer.Option(
        False, "--overschrijf", help="Bestaand profiel overschrijven."
    ),
) -> None:
    """Maak interactief een nieuw profiel aan en sla het op in de XDG-locatie."""
    from iso_audit.memo.theme.elicitation import run_wizard
    from iso_audit.memo.theme.profile import opslaan_profiel

    def _ask(text: str, default: str | None = None) -> str:
        return str(typer.prompt(text) if default is None else typer.prompt(text, default=default))

    def _confirm(text: str, default: bool = False) -> bool:
        return typer.confirm(text, default=default)

    try:
        profiel = run_wizard(ask=_ask, ask_confirm=_confirm)
        pad = opslaan_profiel(profiel, overschrijf=overschrijf)
    except (ProfileError, ValueError, OSError) as exc:
        _fail(str(exc))
    _console.print(f"[green]profiel opgeslagen:[/green] {pad}")


@profile_app.command("list")
def profile_list() -> None:
    """Toon alle profielen in de XDG-locatie."""
    from iso_audit.memo.theme.profile import _profiles_dir

    base = _profiles_dir()
    if not base.is_dir():
        _console.print("(geen profielen)")
        return
    for pad in sorted(base.glob("*.yaml")):
        try:
            p = laad_profiel(pad.stem)
            _console.print(f"{p.slug:20} {p.organization.name}")
        except ProfileError as exc:
            _console.print(f"{pad.stem:20} [red]ongeldig: {exc}[/red]")


@profile_app.command("show")
def profile_show(slug: str = typer.Argument(..., help="Profiel-slug of pad.")) -> None:
    """Toon een profiel (zonder de logo-SVG-blob)."""
    try:
        p = laad_profiel(slug)
    except ProfileError as exc:
        _fail(str(exc))
    dump = p.model_dump()
    dump["brand"]["logo_svg"] = f"<svg … {len(p.brand.logo_svg)} tekens>"
    _console.print(yaml.safe_dump(dump, allow_unicode=True, sort_keys=False))


@profile_app.command("validate")
def profile_validate(slug: str = typer.Argument(..., help="Profiel-slug of pad.")) -> None:
    """Valideer een profiel (schema-versie, kleuren, SVG-veiligheid)."""
    try:
        laad_profiel(slug)
    except ProfileError as exc:
        _fail(str(exc))
    _console.print("[green]profiel is geldig[/green]")
