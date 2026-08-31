"""De omgeving bepaalt of review en auto-triage aanstaan — ook in de UI.

Op 2026-08-31 stond `ISO_AUDIT_REVIEW` op `true` in het manifest, en draaide de review toch
niet: het portaal stuurt per run een harde `true`/`false` mee, want een vinkje kent geen stand
"laat de omgeving beslissen". Een uitgevinkt vakje overrulet daarmee stilletjes het manifest.
De run had 833 bevindingen en nul review-adviezen.

`/instellingen/options` geeft de omgevings-standaard nu mee, zodat de UI de vinkjes ermee kan
vullen. Dat is geen cosmetische fix: zonder die waarde is er in de UI geen enkele manier om te
zien wat de omgeving zegt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.api.conftest import maak_portaal


@pytest.mark.parametrize("waarde,verwacht", [("true", True), ("", False), ("nee", False)])
def test_review_standaard_komt_uit_de_omgeving(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, waarde: str, verwacht: bool
) -> None:
    """`aan` alleen bij een expliciet aan-woord; leeg en onzin tellen als uit."""
    monkeypatch.setenv("ISO_AUDIT_REVIEW", waarde)
    monkeypatch.delenv("ISO_AUDIT_AUTO_TRIAGE", raising=False)
    portaal = maak_portaal(tmp_path)
    standaarden = portaal.get("/instellingen/options").json()["standaarden"]
    assert standaarden["review"] is verwacht
    assert standaarden["auto_triage"] is False


def test_auto_triage_heeft_zijn_eigen_schakelaar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review aan zonder auto-triage moet kunnen: de tweede zeef zonder automatisch afdoen."""
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "true")
    monkeypatch.delenv("ISO_AUDIT_AUTO_TRIAGE", raising=False)
    portaal = maak_portaal(tmp_path)
    standaarden = portaal.get("/instellingen/options").json()["standaarden"]
    assert standaarden == {"review": True, "auto_triage": False}


def test_beide_aan_in_de_omgeving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """De stand die in `deploy/deployment.yaml` staat."""
    monkeypatch.setenv("ISO_AUDIT_REVIEW", "true")
    monkeypatch.setenv("ISO_AUDIT_AUTO_TRIAGE", "true")
    portaal = maak_portaal(tmp_path)
    assert portaal.get("/instellingen/options").json()["standaarden"] == {
        "review": True,
        "auto_triage": True,
    }


def test_de_bestaande_velden_blijven_staan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`norms` en `sources` worden elders gelezen; die mogen niet wegvallen."""
    monkeypatch.delenv("ISO_AUDIT_REVIEW", raising=False)
    portaal = maak_portaal(tmp_path)
    body = portaal.get("/instellingen/options").json()
    assert isinstance(body["norms"], list) and body["norms"]
    assert isinstance(body["sources"], list)


def test_het_manifest_zet_beide_schakelaars_aan() -> None:
    """Het manifest is de plek waar de keuze staat; de code-standaard blijft uit.

    Deze test bewaakt de afspraak "review en auto-triage staan in het portaal altijd aan". Gaat
    hij om, dan is dat een bewuste keuze die in de changelog hoort — niet een regel die iemand
    per ongeluk uit een env-blok haalde.
    """
    import yaml

    docs = [d for d in yaml.safe_load_all(Path("deploy/deployment.yaml").read_text()) if d]
    containers = [
        c
        for d in docs
        if d.get("kind") == "Deployment"
        for c in d["spec"]["template"]["spec"]["containers"]
        if c["name"] == "app"
    ]
    assert containers, "geen app-container in het manifest"
    env = {e["name"]: e.get("value") for e in containers[0]["env"]}
    assert env.get("ISO_AUDIT_REVIEW") == "true"
    assert env.get("ISO_AUDIT_AUTO_TRIAGE") == "true"
    assert env.get("ISO_AUDIT_PROFIEL"), "zonder profielpad valt de clausule-context weg"


def test_de_ui_vult_de_vinkjes_met_de_standaard() -> None:
    """Zonder deze aanroep is de waarde uit de API een dood veld."""
    ui = Path("src/iso_audit/api/ui.html").read_text(encoding="utf-8")
    assert "zetRunStandaarden()" in ui, "de standaard wordt nergens toegepast"
    assert "st.review) wrap.checked = true" in ui
