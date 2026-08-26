"""De output van een audit als downloadbare zip.

Tot 2026-08-26 meldde de export alleen een serverpad —
`PDF: /var/lib/iso-audit/audits/27001_9001-2026-Q3/Auditmemo_management.pdf` — en dat is een pad
in een pod met een read-only filesystem, achter een oauth-proxy. Er was in de hele API geen
enkele download-route; ook de bewijslast-rapporten van 8 MB waren onbereikbaar. Een tool dat
bewijs produceert dat niemand kan ophalen, heeft geen bewijs geproduceerd.

Twee omvangen, want dat is wat een auditor vraagt:

- `memo` — alleen het managementmemo, om te bespreken.
- `bewijslast` — het hele pakket, om te archiveren en te overleggen.

Elke zip draagt een `INHOUD.md` met per bestand waar het vandaan komt en volgens welke regel het
is geselecteerd. Dat is geen beleefdheid: de auditrapporten in `rapporten/` zijn **niet**
audit-gescoped in het datamodel, dus de selectie berust op een afleidbare regel (de normcode van
de audit) en die hoort leesbaar in het pakket te staan in plaats van in de broncode.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from pathlib import Path

SCOPES = ("memo", "bewijslast")
"""De toegestane omvangen. Een onbekende waarde is een fout en geen stille terugval."""

MAX_ZIP_BYTES = 512 * 1024 * 1024
"""Plafond op de zip. De rapportenmap was 8 MB op 2026-08-26; dit is ruim, maar een plafond
zonder getal is geen plafond. Overschrijding is een melding, geen afkapping."""

WERKSETBESTANDEN = ("findings.json", "runs.jsonl", "triage_log.jsonl", "memo-input.yaml")
"""Wat een audit zelf aan bewijs draagt: de werkset, de runs en de append-only triage-trail."""


@dataclass(frozen=True, slots=True)
class Onderdeel:
    """Eén bestand in de zip, met de reden dat het erin zit."""

    bron: Path
    naam_in_zip: str
    herkomst: str


class UitleveringError(Exception):
    """De zip kan niet worden samengesteld."""


def _rapporten_van(audit_dir: Path, run_code: str) -> list[Onderdeel]:
    """De auditrapporten die bij deze audit horen.

    De rapportenmap staat naast de audits en is niet per audit gescheiden — die keuze is ouder
    dan dit bestand. De regel is daarom afleidbaar en expliciet: een rapport hoort bij deze audit
    als de normcode in de bestandsnaam staat. Wat die regel niet vangt, zit er niet in, en het
    manifest zegt dat.
    """
    rapporten = audit_dir.parent.parent / "rapporten"
    if not rapporten.is_dir():
        return []
    return [
        Onderdeel(pad, f"bewijslast/{pad.name}", f"rapportenmap, normcode {run_code!r}")
        for pad in sorted(rapporten.iterdir())
        if pad.is_file() and f"_{run_code}_" in pad.name
    ]


def onderdelen(audit_dir: Path, *, scope: str, run_code: str, memo_pdf: str) -> list[Onderdeel]:
    """Welke bestanden horen in de zip voor deze omvang."""
    if scope not in SCOPES:
        raise UitleveringError(f"onbekende omvang {scope!r}; kies uit {', '.join(SCOPES)}")

    gekozen: list[Onderdeel] = []
    pdf = audit_dir / memo_pdf
    if pdf.is_file():
        gekozen.append(Onderdeel(pdf, pdf.name, "het geëxporteerde managementmemo"))

    if scope == "bewijslast":
        for naam in WERKSETBESTANDEN:
            pad = audit_dir / naam
            if pad.is_file():
                gekozen.append(Onderdeel(pad, f"werkset/{naam}", "de werkset van deze audit"))
        gekozen.extend(_rapporten_van(audit_dir, run_code))
    return gekozen


def _manifest(audit_id: str, scope: str, gekozen: list[Onderdeel]) -> str:
    regels = [
        f"# Inhoud van dit pakket — {audit_id}",
        "",
        f"Omvang: **{scope}**.",
        "",
        "## Selectie",
        "",
        "- Het managementmemo komt uit de audit zelf.",
    ]
    if scope == "bewijslast":
        regels += [
            "- De werksetbestanden (bevindingen, runs, triage-trail) komen uit de audit zelf.",
            "- De auditrapporten komen uit de gedeelde rapportenmap. Die map is niet per audit",
            "  gescheiden; de selectie berust daarom op de normcode in de bestandsnaam. Wat die",
            "  regel niet vangt, zit hier niet in.",
        ]
    regels += ["", "## Bestanden", ""]
    if not gekozen:
        regels.append("Er zit nog niets in dit pakket — het memo is nog niet geëxporteerd.")
    for onderdeel in gekozen:
        regels.append(f"- `{onderdeel.naam_in_zip}` — {onderdeel.herkomst}")
    if scope == "memo" and not any(o.naam_in_zip.endswith(".pdf") for o in gekozen):
        regels += ["", "Het managementmemo is nog niet geëxporteerd."]
    return "\n".join(regels) + "\n"


def bouw_zip(audit_id: str, audit_dir: Path, *, scope: str, run_code: str, memo_pdf: str) -> bytes:
    """Stel de zip samen. Namen zijn relatief; er komt nooit een absoluut pad in."""
    gekozen = onderdelen(audit_dir, scope=scope, run_code=run_code, memo_pdf=memo_pdf)
    totaal = sum(o.bron.stat().st_size for o in gekozen)
    if totaal > MAX_ZIP_BYTES:
        raise UitleveringError(
            f"het pakket is {totaal // 1024 // 1024} MB en het plafond is "
            f"{MAX_ZIP_BYTES // 1024 // 1024} MB; kies omvang 'memo' of ruim de rapportenmap op"
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("INHOUD.md", _manifest(audit_id, scope, gekozen))
        for onderdeel in gekozen:
            zf.write(onderdeel.bron, onderdeel.naam_in_zip)
    return buffer.getvalue()
