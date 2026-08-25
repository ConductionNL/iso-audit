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


def test_een_gecombineerde_run_verliest_geen_9001_clausules() -> None:
    """De samenvoeging was `{**map_9001, **map_27001}` en liet 27001 winnen bij een botsing.

    Achttien nummers bestaan in beide normen, dus de samengevoegde map had 103 ingangen waar er
    121 horen: in een gecombineerde audit bestonden 18 ISO 9001-clausules niet meer — §5.1
    Leiderschap, §6.1 Risico's en kansen, §7.5 Gedocumenteerde informatie, §8.4 Externe
    processen en zo verder. Het rapport claimde intussen "ISO 9001:2015 + ISO 27001:2022".

    Sinds 2026-08-25 draagt elke ingang zijn `varianten` per norm, dus er gaat niets meer
    verloren. De sleutel blijft het clausulenummer, want negen modules gebruiken die map.
    """
    from iso_audit.classification.clause_mapping import laad_clause_map

    map_9001 = laad_clause_map("9001").get("clausules", {})
    samengevoegd = laad_clause_map("beide").get("clausules", {})
    verdwenen = [
        clausule_id
        for clausule_id, veld in map_9001.items()
        if (samengevoegd.get(clausule_id, {}).get("varianten", {}).get("9001", {}).get("titel"))
        != veld.get("titel")
    ]
    assert not verdwenen, (
        f"{len(verdwenen)} ISO 9001-clausules zijn niet meer als 9001-clausule terug te vinden "
        f"in een gecombineerde audit: {verdwenen}"
    )
