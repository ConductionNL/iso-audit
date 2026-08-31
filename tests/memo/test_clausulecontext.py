"""Organisatiecontext per clausule: vastgelegde jurisprudentie in plaats van elke run opnieuw.

Na de volledige run van 2026-08-31 wees de auditor twee NC's aan die het niet zijn:

- **A.8.14, redundantie van informatieverwerkende systemen.** Conduction haalt data bij de bron
  op — een caching-model. Redundantie van eigen systemen is daarmee grotendeels niet van
  toepassing; voor de beperkte eigen data is het een verbeterpunt.
- **A.8.9, configuratiebeheer.** De versies staan in Git. Dat het centraler mag is waar, maar de
  maatregel ontbreekt niet.

Beide keren hetzelfde patroon: er ís een beheersmaatregel, alleen niet gedocumenteerd of
gecentraliseerd. Dat is een verbeterkans en geen non-conformiteit, en zonder die context velt het
model elke run opnieuw hetzelfde verkeerde oordeel.

Waarom in het profiel en niet in de code: dit is klantspecifiek. Een cachende dienstverlener
heeft een ander antwoord op A.8.14 dan een partij die zelf data bewaart. Het profiel is
versiebeheerd, dus de motivering is later na te lezen — en die is **verplicht**: een klasse
verlagen zonder reden is precies het soort stille uitzondering waar een externe auditor op
doorvraagt.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from iso_audit.memo.theme.profile import ProfileError, laad_profiel

_EX = Path("examples/auditmemo/conduction.profile.yaml")


def _profiel_met(context: dict, tmp_path: Path):
    ruw = yaml.safe_load(_EX.read_text(encoding="utf-8"))
    ruw["clausule_context"] = context
    pad = tmp_path / "test.profile.yaml"
    pad.write_text(yaml.safe_dump(ruw, allow_unicode=True), encoding="utf-8")
    return laad_profiel(str(pad))


def test_een_clausule_kan_context_dragen(tmp_path: Path) -> None:
    profiel = _profiel_met(
        {
            "A.8.14": {
                "context": "Wij halen data bij de bron op.",
                "hoogste_klasse": "OFI",
                "motivering": "caching-model; eigen dataopslag is beperkt",
            }
        },
        tmp_path,
    )
    regel = profiel.clausule_context["A.8.14"]
    assert regel.context.startswith("Wij halen")
    assert regel.hoogste_klasse == "OFI"


def test_een_hoogste_klasse_vraagt_een_motivering(tmp_path: Path) -> None:
    """Een klasse verlagen zonder reden is een stille uitzondering."""
    with pytest.raises(ProfileError, match="motivering"):
        _profiel_met({"A.8.9": {"hoogste_klasse": "OFI"}}, tmp_path)


def test_alleen_context_mag_zonder_motivering(tmp_path: Path) -> None:
    """Context geeft het model betere informatie; dat stuurt geen uitkomst."""
    profiel = _profiel_met({"A.8.9": {"context": "Versies staan in Git."}}, tmp_path)
    assert profiel.clausule_context["A.8.9"].hoogste_klasse is None


def test_een_onbekende_klasse_wordt_geweigerd(tmp_path: Path) -> None:
    with pytest.raises(ProfileError):
        _profiel_met(
            {"A.8.9": {"context": "x", "hoogste_klasse": "GEEN_NC", "motivering": "y"}}, tmp_path
        )


def test_een_profiel_zonder_context_blijft_werken(tmp_path: Path) -> None:
    """Bestaande profielen hebben het veld niet; die mogen niet breken."""
    ruw = yaml.safe_load(_EX.read_text(encoding="utf-8"))
    ruw.pop("clausule_context", None)
    pad = tmp_path / "zonder.profile.yaml"
    pad.write_text(yaml.safe_dump(ruw, allow_unicode=True), encoding="utf-8")
    assert laad_profiel(str(pad)).clausule_context == {}


def test_het_conduction_profiel_draagt_de_vastgelegde_jurisprudentie() -> None:
    """A.8.14 en A.8.9 zijn na de run van 2026-08-31 vastgelegd als hooguit een verbeterpunt."""
    profiel = laad_profiel(str(_EX))
    for clausule in ("A.8.14", "A.8.9"):
        regel = profiel.clausule_context[clausule]
        assert regel.hoogste_klasse == "OFI", clausule
        assert regel.motivering.strip(), f"{clausule} verlaagt zonder reden"


def test_nc_mag_niet_als_hoogste_klasse(tmp_path: Path) -> None:
    """Dit veld verlaagt; ophogen naar NC is een auditoordeel dat een mens hoort te vellen."""
    with pytest.raises(ProfileError, match="verlaag"):
        _profiel_met(
            {"A.8.9": {"context": "x", "hoogste_klasse": "NC", "motivering": "y"}}, tmp_path
        )


# --- toepassen in de classificatie ------------------------------------------


def test_de_grens_verlaagt_een_nc_naar_ofi() -> None:
    """Het model kan A.8.14 nog steeds als NC beoordelen; de profielregel verlaagt hem.

    Dat is geen censuur op het oordeel maar vastgelegde jurisprudentie: de auditor heeft
    besloten dat deze eis voor deze organisatie hooguit een verbeterpunt oplevert, met de reden
    erbij en in een versiebeheerd bestand.
    """
    from iso_audit.classification.grenzen import pas_grens_toe

    regel = {"hoogste_klasse": "OFI", "motivering": "caching-model"}
    assert pas_grens_toe("NC", regel) == "OFI"


def test_een_lagere_klasse_blijft_staan() -> None:
    """De grens is een plafond, geen vloer: positief blijft positief."""
    from iso_audit.classification.grenzen import pas_grens_toe

    regel = {"hoogste_klasse": "OFI", "motivering": "x"}
    assert pas_grens_toe("POSITIVE", regel) == "POSITIVE"
    assert pas_grens_toe("OFI", regel) == "OFI"


def test_zonder_grens_verandert_er_niets() -> None:
    from iso_audit.classification.grenzen import pas_grens_toe

    assert pas_grens_toe("NC", {"context": "alleen uitleg"}) == "NC"
    assert pas_grens_toe("NC", None) == "NC"


def test_de_verlaging_is_terug_te_vinden() -> None:
    """Een stille verlaging is precies wat een externe auditor niet accepteert."""
    from iso_audit.classification.grenzen import verlagingsnotitie

    notitie = verlagingsnotitie("NC", "OFI", {"motivering": "caching-model; eigen data beperkt"})
    assert "NC" in notitie and "OFI" in notitie
    assert "caching-model" in notitie
    assert "profiel" in notitie.lower()


def test_de_grens_grijpt_in_bij_het_bouwen_van_een_bevinding() -> None:
    """De ketentest: profielregel erin, verlaagde bevinding eruit, motivering zichtbaar.

    De losse eenheden (`pas_grens_toe`, het profiel) waren al gedekt terwijl de doorgifte van
    `bouw_bevindingen` naar `_bevinding` ontbrak — precies het soort gat waar een regel wél
    bestaat en nooit iets doet.
    """
    from iso_audit.classification.findings import bouw_bevindingen

    profiel = laad_profiel(str(_EX))
    bevindingen = bouw_bevindingen(
        doc={
            "id": "d1",
            "naam": "Infrabeleid",
            "herkomst": "Drive",
            "clausule_normen": [{"clausule": "A.8.14", "norm": "27001"}],
        },
        clausules=["A.8.14"],
        resultaten=[
            {
                "clausule": "A.8.14",
                "classificatie": "NC",
                "beschrijving": "Geen redundantie beschreven.",
                "onderbouwing": "Het document noemt geen uitwijk.",
            }
        ],
        clausule_titels={"A.8.14": {"titel": "Redundantie"}},
        clausule_context=dict(profiel.clausule_context),
    )
    assert [b["classificatie"] for b in bevindingen] == ["OFI"]
    onderbouwing = bevindingen[0]["onderbouwing"]
    assert "Het document noemt geen uitwijk." in onderbouwing, "ruw oordeel mag niet verdwijnen"
    assert "verlaagd naar OFI" in onderbouwing


def test_zonder_profielregel_blijft_de_bevinding_ongemoeid() -> None:
    """Een clausule zonder regel wordt niet aangeraakt — ook de onderbouwing niet."""
    from iso_audit.classification.findings import bouw_bevindingen

    bevindingen = bouw_bevindingen(
        doc={
            "id": "d2",
            "naam": "Beleid",
            "herkomst": "Drive",
            "clausule_normen": [{"clausule": "A.5.1", "norm": "27001"}],
        },
        clausules=["A.5.1"],
        resultaten=[
            {
                "clausule": "A.5.1",
                "classificatie": "NC",
                "beschrijving": "Geen beleid.",
                "onderbouwing": "Niets gevonden.",
            }
        ],
        clausule_titels={"A.5.1": {"titel": "Beleid"}},
        clausule_context=dict(laad_profiel(str(_EX)).clausule_context),
    )
    assert bevindingen[0]["classificatie"] == "NC"
    assert bevindingen[0]["onderbouwing"] == "Niets gevonden."


def test_de_context_komt_in_de_prompt_te_staan() -> None:
    """Het model moet de organisatiecontext lezen, niet alleen de grens achteraf ondergaan."""
    from iso_audit.classification.findings import _bouw_doc_user_prompt

    prompt = _bouw_doc_user_prompt(
        {"naam": "Infrabeleid", "tekst": "..."},
        ["A.8.14", "A.5.1"],
        {"A.8.14": {"titel": "Redundantie"}, "A.5.1": {"titel": "Beleid"}},
        dict(laad_profiel(str(_EX)).clausule_context),
    )
    assert "Organisatiecontext" in prompt
    assert "A.8.14:" in prompt.split("Organisatiecontext")[1]
    # Een clausule zonder context krijgt geen lege regel in het blok.
    assert "A.5.1:" not in prompt.split("Organisatiecontext")[1]


def test_zonder_context_blijft_de_prompt_letterlijk_gelijk() -> None:
    """Geen profiel betekent geen verandering aan wat het model te zien krijgt."""
    from iso_audit.classification.findings import _bouw_doc_user_prompt

    doc = {"naam": "Beleid", "tekst": "abc"}
    titels = {"A.5.1": {"titel": "Beleid"}}
    assert _bouw_doc_user_prompt(doc, ["A.5.1"], titels, {}) == _bouw_doc_user_prompt(
        doc, ["A.5.1"], titels
    )


def test_beide_clausules_delen_een_thema_zodat_de_memo_ze_bundelt() -> None:
    """Het punt van de auditor: A.8.14 en A.8.9 zijn één verbeterkans, geen twee opmerkingen."""
    from iso_audit.classification.thema import THEMA_LIJST, bepaal_thema, thema_uit_profiel

    context = dict(laad_profiel(str(_EX)).clausule_context)
    themas = {c: thema_uit_profiel({"clausule": c}, context) for c in ("A.8.14", "A.8.9")}
    assert len(set(themas.values())) == 1, themas
    thema = next(iter(themas.values()))
    assert thema in THEMA_LIJST, "een thema buiten de taxonomie bundelt met niets"

    # Zonder het profiel vallen ze uit elkaar — dat is precies waarom het profiel nodig is.
    heuristiek = {
        bepaal_thema({"clausule": "A.8.14", "beschrijving": "redundantie en continuïteit"}),
        bepaal_thema({"clausule": "A.8.9", "beschrijving": "configuratiebeheer ontbreekt"}),
    }
    assert len(heuristiek) == 2, heuristiek


def test_een_onbekend_thema_in_het_profiel_wordt_geweigerd() -> None:
    """Vrije tekst zou per profiel een eigen thema opleveren; dan bundelt de memo niets meer."""
    ruw = yaml.safe_load(_EX.read_text(encoding="utf-8"))
    ruw["clausule_context"]["A.8.9"]["thema"] = "Documentatie graag beter"
    pad = Path(tempfile.mkdtemp()) / "fout.profile.yaml"
    pad.write_text(yaml.safe_dump(ruw, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ProfileError, match="onbekend thema"):
        laad_profiel(str(pad))


def test_een_clausule_zonder_profielthema_houdt_de_heuristiek() -> None:
    """De profielregel gaat voor, maar alleen waar hij bestaat."""
    from iso_audit.classification.thema import thema_uit_profiel

    context = dict(laad_profiel(str(_EX)).clausule_context)
    assert thema_uit_profiel({"clausule": "A.5.1"}, context) == ""
    assert thema_uit_profiel({"clausule": "A.8.9"}, None) == ""
