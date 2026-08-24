"""Markdown → standalone HTML voor visuele preview van het auditrapport.

Gebruikt `python-markdown` met de standaard `tables`, `toc`, `fenced_code`
en `attr_list` extensies. Minimal CSS inline — geen externe afhankelijkheden
bij render-tijd.

Gemigreerd uit `Ops_to_Biz/audit/md_to_html.py` per milestone B §2.5.2.

Gebruik:
    python -m iso_audit.reporting.md_to_html <md_pad> [--output <html_pad>]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import markdown

CSS = """
:root {
  --fg: #1a1a1a;
  --bg: #ffffff;
  --muted: #666;
  --border: #e1e4e8;
  --nc: #d73a49;
  --ofi: #e36209;
  --pos: #22863a;
  --accent: #0969da;
  --code-bg: #f6f8fa;
}
html, body {
  margin: 0;
  padding: 0;
  color: var(--fg);
  background: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.55;
}
.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 260px;
  gap: 2.5em;
  max-width: 1280px;
  margin: 0 auto;
  padding: 2em;
  align-items: start;
}
main { min-width: 0; }
h1 { border-bottom: 2px solid var(--border); padding-bottom: 0.3em; }
h2 { border-bottom: 1px solid var(--border); padding-bottom: 0.2em; margin-top: 2em; }
h3 { color: #111; margin-top: 1.6em; }
h4 {
  color: var(--accent);
  margin-top: 1em;
  padding: 0.3em 0.6em;
  background: #f0f6ff;
  border-left: 3px solid var(--accent);
  border-radius: 3px;
}
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th, td {
  border: 1px solid var(--border);
  padding: 0.4em 0.8em;
  text-align: left;
  vertical-align: top;
}
th { background: #f6f8fa; }
blockquote {
  margin: 0.5em 0;
  padding: 0.2em 1em;
  color: #333;
  border-left: 3px solid var(--border);
  background: #fafbfc;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
em { color: var(--muted); }
code { background: var(--code-bg); padding: 0.1em 0.3em; border-radius: 3px; font-size: 0.9em; }
hr { border: none; border-top: 1px solid var(--border); margin: 2em 0; }

/* Sticky TOC in de tweede grid-kolom */
.toc {
  position: sticky;
  top: 1em;
  max-height: calc(100vh - 2em);
  overflow-y: auto;
  padding: 0.8em 1em;
  border: 1px solid var(--border);
  background: #fafbfc;
  font-size: 0.85em;
  border-radius: 4px;
}
.toc ul { padding-left: 1em; margin: 0.2em 0; }
.toc > ul { padding-left: 0; list-style: none; }
.toc li { margin: 0.15em 0; }

/* Responsive: TOC onder content op smalle schermen */
@media (max-width: 1100px) {
  .page { grid-template-columns: 1fr; gap: 1em; }
  .toc { position: static; max-height: none; order: -1; }
}
@page {
  size: A4;
  margin: 1.5cm 1.2cm;
}
@media print {
  .toc { display: none; }
  /* `display: block` is hier geen opmaakvoorkeur maar de rendertijd. WeasyPrint legt een
     grid-container niet over paginagrenzen uiteen en probeert het hele rapport als één
     grid-item te plaatsen: gemeten op 2026-08-24 op het rapport van die dag (345 pagina's)
     ruim acht minuten met grid tegen 16 seconden met block. Zie `reporting/html_to_pdf.py`. */
  .page { display: block; grid-template-columns: 1fr; max-width: none; padding: 0; }
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="page">
<main>
{body}
</main>
{toc}
</div>
</body>
</html>
"""


def converteer(
    md_pad: str | os.PathLike[str],
    html_pad: str | os.PathLike[str] | None = None,
) -> str:
    """Lees Markdown van `md_pad`, schrijf standalone HTML naar `html_pad`.

    Retourneert het uiteindelijke HTML-pad. Als `html_pad` niet is opgegeven
    wordt het naast het Markdown-bestand geschreven met dezelfde naam.
    """
    md_path = Path(md_pad)
    if not md_path.is_file():
        raise FileNotFoundError(str(md_path))

    tekst = md_path.read_text(encoding="utf-8")

    md = markdown.Markdown(
        extensions=["tables", "fenced_code", "attr_list", "toc"],
        extension_configs={"toc": {"toc_depth": "2-4"}},
    )
    body = md.convert(tekst)
    # `Markdown.toc` wordt door de `toc`-extensie als runtime-attribuut gezet;
    # mypy ziet dat niet in de stubs, vandaar de getattr-form.
    toc_html: str = getattr(md, "toc", "") or ""
    toc = f'<nav class="toc"><strong>Inhoud</strong>{toc_html}</nav>' if toc_html else ""

    titel = md_path.stem
    html = HTML_TEMPLATE.format(title=titel, css=CSS, toc=toc, body=body)

    out_path = Path(html_pad) if html_pad is not None else md_path.with_suffix(".html")
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Markdown → standalone HTML preview")
    parser.add_argument("md_pad")
    parser.add_argument("--output", "-o", default=None, help="HTML-uitvoerpad (default: naast .md)")
    args = parser.parse_args()
    html_pad = converteer(args.md_pad, args.output)
    print(f"HTML geschreven: {html_pad}")
    print(f"Open in browser: file://{os.path.abspath(html_pad)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
