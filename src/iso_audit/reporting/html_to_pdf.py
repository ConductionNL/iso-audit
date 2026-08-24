"""HTML → PDF converter via WeasyPrint.

Tot 2026-08-24 liep dit via Chrome headless, met in de docstring de reden dat WeasyPrint
"traag was op lange rapporten met complex grid-layout". Die observatie was juist, en de
oorzaak bleek één CSS-declaratie: WeasyPrint legt een grid-container niet over paginagrenzen
uiteen, dus `.page { display: grid }` liet hem het hele rapport als één grid-item plaatsen.
Gemeten op het rapport van die dag (767 KB HTML, 345 pagina's): langer dan acht minuten met
grid, 16 seconden met `display: block` in het print-blok. Zie `md_to_html.CSS`.

Waarom dat Chrome vervangt en niet aanvult: Chrome stond niet in het image, en de enige plek
waar dat bleek was een `logger.warning` aan het eind van een run — de PDF ontbrak stil terwijl
de rest van het rapport er wel stond. Chromium erbij zetten kost 338 MB aan libs plus fonts en
zet een netwerk-capabele renderer in een container die onder 27001-scope valt. WeasyPrint is al
een dependency (de memo-render gebruikt hem) en zijn systeembibliotheken staan al in het
Dockerfile, dus `uv sync` en `docker build` garanderen samen dat de renderer aanwezig is.

Gemigreerd uit `Ops_to_Biz/audit/html_to_pdf.py` per milestone B §2.5.2.

Gebruik:
    python -m iso_audit.reporting.html_to_pdf <html_pad> [--output <pdf_pad>]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def converteer(
    html_pad: str | os.PathLike[str],
    pdf_pad: str | os.PathLike[str] | None = None,
) -> str:
    """Render HTML naar PDF.

    Retourneert het PDF-pad. Bij `pdf_pad=None` wordt het naast het HTML geschreven met
    `.pdf`-extensie.
    """
    html_path = Path(html_pad)
    if not html_path.is_file():
        raise FileNotFoundError(str(html_path))

    out_path = Path(pdf_pad) if pdf_pad is not None else html_path.with_suffix(".pdf")

    # Import binnen de functie: WeasyPrint trekt bij import cairo en pango aan, en dat is
    # verspild werk in elk proces dat deze module alleen importeert om `converteer` te kunnen
    # noemen. Zelfde reden als de late imports in `pipeline._converteer_md_naar_html_docx_pdf`.
    from weasyprint import HTML

    HTML(filename=str(html_path.resolve())).write_pdf(str(out_path.resolve()))
    return str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="HTML → PDF via WeasyPrint")
    parser.add_argument("html", help="pad naar het HTML-bestand")
    parser.add_argument("--output", help="pad voor de PDF (standaard: naast het HTML)")
    args = parser.parse_args()
    try:
        pad = converteer(args.html, args.output)
    except FileNotFoundError as fout:
        print(f"fout: bestand niet gevonden: {fout}", file=sys.stderr)
        return 1
    print(pad)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
