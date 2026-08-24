"""De norm-DB-export moet gelijk lopen met de repo-bron.

`examples/norms/*.yaml` is een export uit `iso_audit.data.normteksten`. Tot 2026-08-24 werd die
met de hand bijgehouden en bevatte hij **13 van de 121** clausules. Dat gaf geen fout, alleen
verkeerde antwoorden:

- `iso-audit memo` weigerde op de echte dataset ("Clausule '10.3' ontbreekt in
  iso-9001-2015"), en dat las als een licentieprobleem terwijl de tekst in de repo staat.
- `run_job._resolve_standard()` bepaalt met deze DB bij welke norm een bevinding hoort. Met 13
  clausules zei de DB bijna altijd "niet in 27001" en viel alles terug op de 9001-default:
  **448 van de 903 bevindingen droegen de verkeerde norm**, waaronder clausule 8.24
  (cryptografie, Annex A van 27001) als ISO 9001:2015.

Een achterlopende export is niet zichtbaar zonder deze test — dat is precies waarom hij bestaat.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import yaml

from iso_audit.data import normteksten


def _laad_generator() -> ModuleType:
    """Laad het script via zijn pad — de bestandsnaam heeft koppeltekens.

    Bewust geen tweede kopie met underscores naast het script: twee bestanden met dezelfde
    inhoud lopen uiteen, en dat is precies het probleem dat deze test bewaakt.
    """
    pad = Path("scripts/genereer-norm-db.py")
    spec = importlib.util.spec_from_file_location("genereer_norm_db", pad)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


genereer_norm_db = _laad_generator()


@pytest.mark.parametrize(
    ("slug", "bron"),
    [
        ("iso-9001-2015", normteksten.NORMTEKSTEN_9001),
        ("iso-27001-2022", normteksten.NORMTEKSTEN_27001),
    ],
)
def test_export_bevat_elke_clausule_uit_de_bron(slug: str, bron: dict[str, object]) -> None:
    gegevens = yaml.safe_load(Path(f"examples/norms/{slug}.yaml").read_text(encoding="utf-8"))
    geëxporteerd = set(gegevens["clauses"])
    ontbreekt = sorted(set(bron) - geëxporteerd)
    assert not ontbreekt, (
        f"{len(ontbreekt)} clausules staan in de bron maar niet in de export: {ontbreekt[:10]} — "
        "draai `uv run python scripts/genereer-norm-db.py`"
    )


def test_export_is_bij_de_tijd() -> None:
    """Byte-vergelijking: elke wijziging in de bron moet opnieuw geëxporteerd worden."""
    assert genereer_norm_db.main(["--check"]) == 0, (
        "de norm-DB loopt achter op iso_audit.data.normteksten — "
        "draai `uv run python scripts/genereer-norm-db.py`"
    )


def test_elke_clausule_heeft_een_titel_en_een_tekst() -> None:
    """Een lege tekst maakt de memo-weigering onterecht: de clausule bestaat wél."""
    leeg: list[str] = []
    for slug in ("iso-9001-2015", "iso-27001-2022"):
        gegevens = yaml.safe_load(Path(f"examples/norms/{slug}.yaml").read_text(encoding="utf-8"))
        for clausule_id, veld in gegevens["clauses"].items():
            if not veld.get("text_nl") or not veld.get("title_nl"):
                leeg.append(f"{slug}:{clausule_id}")
    assert not leeg, f"clausules zonder titel of tekst: {leeg[:10]}"


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bekend en gemeten defect (2026-08-24), nog niet gerepareerd: `laad_clause_map('beide')` "
        "voegt de twee maps samen met `{**map_9001, **map_27001}`, waardoor 27001 de 9001-ingang "
        "overschrijft bij een botsend nummer. In een gecombineerde audit worden daardoor 18 van "
        "de 28 ISO 9001-clausules nooit getoetst — waaronder §5.1 Leiderschap, §6.1 Risico's en "
        "kansen, §7.5 Gedocumenteerde informatie en §8.4 Externe processen. Repareren vraagt dat "
        "een clausule door (norm, id) wordt geïdentificeerd in plaats van door id alleen, en dat "
        "raakt de opslag, de classificatie-prompt en de UI. Zie de openstaande change. Deze test "
        "is `strict`: zodra het gerepareerd is faalt hij, en moet de markering weg."
    ),
)
def test_een_gecombineerde_run_verliest_geen_9001_clausules() -> None:
    from iso_audit.classification.clause_mapping import laad_clause_map

    map_9001 = laad_clause_map("9001").get("clausules", {})
    samengevoegd = laad_clause_map("beide").get("clausules", {})
    verdwenen = [
        clausule_id
        for clausule_id, veld in map_9001.items()
        if samengevoegd.get(clausule_id, {}).get("titel") != veld.get("titel")
    ]
    assert not verdwenen, (
        f"{len(verdwenen)} ISO 9001-clausules worden in een gecombineerde audit vervangen door "
        f"hun 27001-naamgenoot en dus nooit getoetst: {verdwenen}"
    )
