"""Console-script entry-point voor iso-audit.

Subcommands (§2.6.1):

- ``pipeline``       — voer de volledige audit-pipeline uit
- ``doctor``         — controleer of de omgeving correct geconfigureerd is
- ``setup-template`` — eenmalige Drive-template-aanmaak

Verder:

- ``--source`` flag (§2.6.2): verplicht voor ``pipeline``, multi-value,
  met ``ISO_AUDIT_DEFAULT_SOURCE``-env-var-fallback (INFO-log bij
  fallback). Voor ``setup-template`` en ``doctor`` is ``--source`` niet
  relevant.

``iso_audit.__main__`` en directe ``python -m iso_audit.pipeline``-call
delegeren beide naar deze ``main()``.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys

from dotenv import load_dotenv

from iso_audit import __version__

# Laad `.env` zodat env-vars uit de project-root beschikbaar zijn voor
# `doctor`, `pipeline`, `setup-template`. `pipeline.py` laadt ze ook bij
# eigen import-time, maar `doctor` raakt `pipeline` niet aan — daarom hier.
load_dotenv()

logger = logging.getLogger(__name__)

_SOURCE_ENV_VAR = "ISO_AUDIT_DEFAULT_SOURCE"
_MODE_ENV_VAR = "ISO_AUDIT_DEFAULT_MODE"
_NOTIFIER_ENV_VAR = "ISO_AUDIT_DEFAULT_NOTIFIER"
_VALID_MODES: tuple[str, ...] = ("autonoom", "integer")


def _bekende_bronnen() -> list[str]:
    """Alle ingest-bronnen die de pipeline accepteert."""
    from iso_audit.ingest import beschikbare_bronnen

    return beschikbare_bronnen()


def _bekende_notifiers() -> list[str]:
    """Alle geregistreerde Notifier-adapters."""
    # Trigger imports zodat hun @register-decorator draait.
    import iso_audit.notifiers.email
    import iso_audit.notifiers.slack  # noqa: F401
    from iso_audit import notifiers

    return notifiers.available()


def _resolve_mode(args_mode: str | None) -> str:
    """Bepaal de actieve mode-naam uit CLI of `ISO_AUDIT_DEFAULT_MODE`-env."""
    if args_mode:
        return args_mode
    env_val = os.environ.get(_MODE_ENV_VAR, "").strip()
    if env_val:
        logger.info("--mode niet opgegeven; fallback naar %s=%s", _MODE_ENV_VAR, env_val)
        if env_val not in _VALID_MODES:
            print(
                f"iso-audit: onbekende mode {env_val!r} via env. Verwacht een van {_VALID_MODES}.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        return env_val
    print(
        f"iso-audit: missing required argument: --mode "
        f"(opties: {_VALID_MODES}). "
        f"Alternatief: zet env-var {_MODE_ENV_VAR}.",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _resolve_notifier(args_notifier: str | None, mode_naam: str) -> str | None:
    """Bepaal notifier-naam; vereist alleen bij `mode='integer'`."""
    if mode_naam == "autonoom":
        if args_notifier:
            logger.warning("notifier ignored in autonoom mode (kreeg %r)", args_notifier)
        return None

    # mode == integer
    if args_notifier:
        chosen = args_notifier
    else:
        env_val = os.environ.get(_NOTIFIER_ENV_VAR, "").strip()
        if not env_val:
            print(
                "iso-audit: missing required argument when --mode integer: "
                f"--notifier (fallback env-var {_NOTIFIER_ENV_VAR}).",
                file=sys.stderr,
            )
            raise SystemExit(2)
        logger.info(
            "--notifier niet opgegeven; fallback naar %s=%s",
            _NOTIFIER_ENV_VAR,
            env_val,
        )
        chosen = env_val

    bekende = _bekende_notifiers()
    if chosen not in bekende:
        print(
            f"iso-audit: onbekende notifier {chosen!r}. Beschikbaar: {bekende}.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return chosen


def _construeer_mode(mode_naam: str, notifier_naam: str | None) -> object:
    """Bouw de juiste Mode-instantie met (voor integer) een Notifier via DI."""
    from iso_audit.modes.autonoom import AutonoomMode
    from iso_audit.modes.integer import IntegerMode
    from iso_audit.store import initialiseer, verbinding

    conn = verbinding()
    initialiseer(conn)
    if mode_naam == "autonoom":
        return AutonoomMode(conn=conn)

    # integer
    assert notifier_naam is not None
    from iso_audit import notifiers as notifier_registry

    notifier_class = notifier_registry.get(notifier_naam)
    notifier = notifier_class()
    return IntegerMode(notifier=notifier, conn=conn)


def _resolve_sources(args_sources: list[str] | None) -> list[str]:
    """Bepaal de actieve source-set uit CLI of `ISO_AUDIT_DEFAULT_SOURCE`-env.

    Returnt een gesorteerde, deduplicate lijst.
    Raises `SystemExit(2)` als er geen sources zijn opgegeven of als een
    onbekende source genoemd wordt.
    """
    bekende = set(_bekende_bronnen())

    sources: list[str]
    if args_sources:
        sources = list(args_sources)
    else:
        env_val = os.environ.get(_SOURCE_ENV_VAR, "").strip()
        if not env_val:
            print(
                f"iso-audit: --source is verplicht (of zet {_SOURCE_ENV_VAR}). "
                f"Beschikbare bronnen: {sorted(bekende)}.",
                file=sys.stderr,
            )
            raise SystemExit(2)
        sources = [s.strip() for s in env_val.split(",") if s.strip()]
        logger.info("--source niet opgegeven; fallback naar %s=%s", _SOURCE_ENV_VAR, env_val)

    onbekend = [s for s in sources if s not in bekende]
    if onbekend:
        print(
            f"iso-audit: onbekende source(s) {onbekend}. Beschikbare: {sorted(bekende)}.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return sorted(set(sources))


def _run_pipeline(args: argparse.Namespace) -> int:
    from iso_audit import pipeline

    if args.local_only:
        # Bestond in de oude codebase (`python -m audit.pipeline --local-only`) en werkt
        # nog in `pipeline.main()`, maar was bij de verhuizing niet doorgezet naar de
        # `iso-audit`-CLI. Daardoor kende de gedocumenteerde ingang de dry-run niet meer.
        logger.info("Local-only: alleen een lokaal rapport uit de bestaande DB.")
        pad = pipeline.run_local_only(args.norm)
        logger.info("Rapport geschreven: %s", pad)
        return 0

    if args.report_only:
        # Near-idempotente regeneratie: alleen rapport uit bestaande DB, geen
        # ingest/classificatie/Drive/Miro. --source/--mode zijn dan niet vereist.
        logger.info(
            "Report-only: rapport regenereren uit bestaande DB "
            "(geen ingest, classificatie, Drive of Miro)."
        )
        pipeline.run_report_only(args.norm, scherpte=args.scherpte, thema_llm=args.thema_llm)
        return 0

    sources = _resolve_sources(args.source)
    mode_naam = _resolve_mode(args.mode)
    notifier_naam = _resolve_notifier(args.notifier, mode_naam)
    mode = _construeer_mode(mode_naam, notifier_naam)
    logger.info(
        "Actieve sources: %s | mode=%s | notifier=%s",
        sources,
        mode_naam,
        notifier_naam or "-",
    )

    pipeline.run_audit(
        args.norm,
        no_review=args.no_review,
        write_sheets=args.write_sheets,
        chapter=args.chapter,
        scherpte=args.scherpte,
        review=args.review,
        review_steekproef=args.review_steekproef,
        auto_triage=args.auto_triage,
        thema_llm=args.thema_llm,
        rehash=args.rehash,
        dry_run_cost=args.dry_run_cost,
        mode=mode,  # type: ignore[arg-type]
        sources=sources,
    )
    return 0


def _run_setup_template(_args: argparse.Namespace) -> int:
    from iso_audit import pipeline

    pipeline._valideer_env()
    pipeline.run_setup_template()
    return 0


def _run_doctor(_args: argparse.Namespace) -> int:
    """Check of de omgeving correct is geconfigureerd."""
    ok = True

    if shutil.which("gws"):
        print("[ok]  gws CLI gevonden in PATH")
    else:
        print("[fail] gws CLI niet gevonden in PATH")
        ok = False

    sleutels = [
        "AUDIT_NORM",
        "AUDIT_DB_PATH",
        "AUDIT_DRIVE_FOLDER_ID",
        "ANTHROPIC_API_KEY",
        "MIRO_BOARD_ID",
        "SLACK_WEBHOOK_URL",
        "SLACK_BOT_TOKEN",
        "AUDIT_NOTIFIER_EMAIL",
        "SMTP_HOST",
    ]
    print()
    print("Omgevingsvariabelen:")
    for k in sleutels:
        v = os.environ.get(k, "")
        getoond = "[set]" if v else "[leeg]"
        print(f"  {k:<25} {getoond}")

    print()
    bronnen = _bekende_bronnen()
    print(f"Geregistreerde sources: {bronnen}")

    print()
    notifier_namen = _bekende_notifiers()
    print(f"Geregistreerde notifiers: {notifier_namen}")
    for naam in notifier_namen:
        try:
            from iso_audit import notifiers as notifier_registry

            instance = notifier_registry.get(naam)()
            health = instance.healthcheck()
            status = health.get("status", "?")
            tag = "[ok]" if status == "ok" else "[fail]"
            print(f"  {tag:<7} {naam}: {health}")
            if status != "ok":
                ok = False
        except Exception as e:
            print(f"  [fail] {naam}: {e}")
            ok = False

    return 0 if ok else 1


def _voeg_pipeline_args_toe(parser: argparse.ArgumentParser) -> None:
    """Pipeline-specifieke argumenten."""
    parser.add_argument(
        "--source",
        action="append",
        default=None,
        help=(
            "Source-adapter(s) om uit te lezen. Meerdere keren opgeven mag. "
            f"Fallback: env-var {_SOURCE_ENV_VAR} (komma-gescheiden)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=_VALID_MODES,
        default=None,
        help=(
            f"Runmodus. Verplicht; fallback: env-var {_MODE_ENV_VAR}. "
            "autonoom: cron-friendly, geen mens-in-de-lus. "
            "integer: escaleert hoog-risico beslissingen via --notifier."
        ),
    )
    parser.add_argument(
        "--notifier",
        default=None,
        help=(
            "Notifier-adapter voor integer-modus (slack/email). "
            f"Verplicht bij --mode integer; fallback: env-var {_NOTIFIER_ENV_VAR}."
        ),
    )
    parser.add_argument(
        "--norm",
        choices=["9001", "27001", "beide"],
        default=os.environ.get("AUDIT_NORM", "beide"),
        help="Toepasselijke norm (default: waarde van AUDIT_NORM in .env)",
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
        help="Classificatie-scherpte: 1.0=strikt (default), 0.5=genuanceerd",
    )
    parser.add_argument(
        "--chapter",
        default=None,
        metavar="N",
        help="Beperk tot een hoofdstuk (bv. 4, 8, 5.1).",
    )
    parser.add_argument(
        "--thema-llm",
        action="store_true",
        help="Verfijn thema-toekenning via LLM voor 'Overig'-findings",
    )
    parser.add_argument(
        "--rehash",
        action="store_true",
        help="Ignoreer checkpoint en herclassificeer alles (UPSERT)",
    )
    # Aan/uit als drie standen: expliciet aan, expliciet uit, of niets zeggen en de
    # omgeving laten beslissen. Een `store_true`-vlag kan dat derde niet — die is altijd
    # False als hij ontbreekt, en dan kan een expliciete `--geen-review` de env-var niet
    # overstemmen. Zie `classification/review.ReviewInstelling`.
    review = parser.add_mutually_exclusive_group()
    review.add_argument(
        "--review",
        dest="review",
        action="store_const",
        const=True,
        help="Autonome review aan: per clausule een tweede oordeel op een zwaarder model",
    )
    review.add_argument(
        "--geen-review",
        dest="review",
        action="store_const",
        const=False,
        help="Autonome review uit, ook als ISO_AUDIT_REVIEW aan staat",
    )
    parser.set_defaults(review=None)
    auto = parser.add_mutually_exclusive_group()
    auto.add_argument(
        "--auto-triage",
        dest="auto_triage",
        action="store_const",
        const=True,
        help=(
            "Doe het onbetwiste deel automatisch af: bevestigde positieve bevindingen. "
            "Nooit een NC en nooit een verlaging — die blijven bij de auditor"
        ),
    )
    auto.add_argument(
        "--geen-auto-triage",
        dest="auto_triage",
        action="store_const",
        const=False,
        help="Auto-triage uit, ook als ISO_AUDIT_AUTO_TRIAGE aan staat",
    )
    parser.set_defaults(auto_triage=None)
    parser.add_argument(
        "--review-steekproef",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Beoordeel alleen de N zwaarste clausules — meet wat de review oplevert "
            "vóór je alle clausules op een zwaar model zet"
        ),
    )
    parser.add_argument(
        "--dry-run-cost",
        action="store_true",
        help="Toon alleen kostenschatting — geen API-calls voor LLM",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help=(
            "Regenereer alleen het rapport uit de bestaande bevindingen-DB "
            "(geen ingest/classificatie/Drive/Miro). --source/--mode niet vereist. "
            "Near-idempotent: bedoeld voor iteratie op rapporttaal."
        ),
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help=(
            "Lees en classificeer niets; genereer alleen een lokaal rapport uit de "
            "bestaande DB. Geen Drive, geen Miro, geen Claude. --source/--mode niet vereist."
        ),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iso-audit",
        description="ISO 9001 + 27001 audit pipeline.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_pipe = sub.add_parser("pipeline", help="Voer de auditpipeline uit")
    _voeg_pipeline_args_toe(p_pipe)
    p_pipe.set_defaults(func=_run_pipeline)

    p_doc = sub.add_parser("doctor", help="Controleer omgeving en configuratie")
    p_doc.set_defaults(func=_run_doctor)

    p_tmpl = sub.add_parser("setup-template", help="Maak het Drive-template eenmalig aan")
    p_tmpl.set_defaults(func=_run_setup_template)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Hoofdingang voor de ``iso-audit`` console-script.

    Returnt een exit-code (``0`` succes, ``2`` argument-fout).
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # memo/profile draaien als Typer-subapp achter dezelfde console-script.
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in ("memo", "draft", "profile", "ui"):
        from iso_audit.memo.cli import app as memo_app

        memo_app(args_list)  # Typer/click handelt zelf de exit af
        return 0

    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
