"""Tests voor de audit-registry, runs en het dashboard-overzicht (change portal-dashboard)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from iso_audit.api import overzicht as ov
from iso_audit.api import runs as runs_mod
from iso_audit.api.registry import AuditRegistry, RegistryError, audit_id


def _kandidaat(**kw: object) -> dict[str, object]:
    basis: dict[str, object] = {
        "id": "x1",
        "severity": "NC",
        "standard": "iso-9001-2015",
        "clause": "10.2",
        "title": "Correctieve maatregelen",
        "description": "Effectiviteit niet geëvalueerd.",
        "source": "drive",
    }
    basis.update(kw)
    return basis


# --- audit_id -------------------------------------------------------------


@pytest.mark.parametrize(
    ("norm", "periode", "verwacht"),
    [("9001", "2026-Q3", "9001-2026-Q3"), ("27001", "2026-h2", "27001-2026-H2")],
)
def test_audit_id(norm: str, periode: str, verwacht: str) -> None:
    assert audit_id([norm], periode) == verwacht


@pytest.mark.parametrize("periode", ["najaar", "2026", "Q3", "2026-Q", "26-Q3"])
def test_audit_id_weigert_onsorteerbare_periode(periode: str) -> None:
    """Vrije tekst maakt sorteren op periode onbetrouwbaar — dus hard weigeren."""
    with pytest.raises(RegistryError, match="periode"):
        audit_id(["9001"], periode)


def test_audit_id_weigert_lege_norm() -> None:
    with pytest.raises(RegistryError, match=r"[Nn]orm"):
        audit_id(["  "], "2026-Q3")


# --- aanmaken -------------------------------------------------------------


def test_maak_audit_legt_aanmaker_vast(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="auditor@conduction.nl")

    manifest = json.loads((r.pad(aid) / "audit.json").read_text(encoding="utf-8"))
    assert manifest["aangemaakt_door"] == "auditor@conduction.nl"
    assert manifest["normen"] == ["9001"]
    assert manifest["periode"] == "2026-Q3"
    # Lege maar geldige werkset, zodat AuditSession direct te openen is.
    assert json.loads((r.pad(aid) / "findings.json").read_text(encoding="utf-8")) == []


def test_dubbel_id_faalt_en_laat_bestaande_ongemoeid(tmp_path: Path) -> None:
    """Geen stil suffix: twee audits met dezelfde norm én periode is een vergissing."""
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")
    (r.pad(aid) / "findings.json").write_text(json.dumps([_kandidaat()]), encoding="utf-8")

    with pytest.raises(RegistryError, match="bestaat al"):
        r.maak(normen=["9001"], periode="2026-Q3", door="b@conduction.nl")

    assert len(json.loads((r.pad(aid) / "findings.json").read_text(encoding="utf-8"))) == 1
    assert len(list(tmp_path.iterdir())) == 1


def test_eis_onbekende_audit(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="bestaat niet"):
        AuditRegistry(tmp_path).eis("9001-2026-Q3")


@pytest.mark.parametrize("aid", ["../ontsnap", "a/b", "", "."])
def test_pad_weigert_ontsnapping(tmp_path: Path, aid: str) -> None:
    with pytest.raises(RegistryError, match="Ongeldig audit-id"):
        AuditRegistry(tmp_path).pad(aid)


# --- aanvullende runs en dedup -------------------------------------------


def test_tweede_run_vult_aan_en_behoudt_triage(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")
    d = r.pad(aid)

    runs_mod.voeg_toe(d, [_kandidaat(id="f1")])
    # Auditor triageert.
    data = json.loads((d / "findings.json").read_text(encoding="utf-8"))
    data[0]["triage_status"] = "valide"
    (d / "findings.json").write_text(json.dumps(data), encoding="utf-8")

    toegevoegd, overgeslagen = runs_mod.voeg_toe(
        d, [_kandidaat(id="f2", source="jira", clause="9.2")]
    )
    assert (toegevoegd, overgeslagen) == (1, 0)

    na = json.loads((d / "findings.json").read_text(encoding="utf-8"))
    assert len(na) == 2
    assert na[0]["triage_status"] == "valide", "eerder triage-werk is weggegooid"


def test_duplicaat_wordt_overgeslagen_en_geteld(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))

    runs_mod.voeg_toe(d, [_kandidaat(id="f1")])
    # Zelfde norm/clausule/bron/titel — alleen een ander id en andere beschrijving.
    toegevoegd, overgeslagen = runs_mod.voeg_toe(
        d, [_kandidaat(id="anders", description="andere tekst")]
    )
    assert (toegevoegd, overgeslagen) == (0, 1)
    assert len(json.loads((d / "findings.json").read_text(encoding="utf-8"))) == 1


def test_dedup_negeert_hoofdletters_en_dubbele_spaties(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))
    runs_mod.voeg_toe(d, [_kandidaat(title="Correctieve maatregelen")])
    _, overgeslagen = runs_mod.voeg_toe(d, [_kandidaat(title="  correctieve   MAATREGELEN ")])
    assert overgeslagen == 1


def test_dedup_is_reproduceerbaar(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))
    kandidaten = [_kandidaat(id="a"), _kandidaat(id="b", clause="9.2")]
    eerste = runs_mod.voeg_toe(d, kandidaten)
    tweede = runs_mod.voeg_toe(d, kandidaten)
    assert eerste == (2, 0)
    assert tweede == (0, 2)


# --- run-registratie -----------------------------------------------------


def test_run_record_is_append_only(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))

    runs_mod.registreer(d, door="a@conduction.nl", modus="sim", norm="9001", bronnen=["drive"])
    eerste = runs_mod.lijst(d)
    runs_mod.registreer(
        d, door="b@conduction.nl", modus="live", norm="9001", bronnen=["drive", "jira"]
    )
    tweede = runs_mod.lijst(d)

    assert len(tweede) == 2
    assert tweede[0] == eerste[0], "oudere run-regel is gemuteerd"
    assert tweede[1]["run_id"] == "run-0002"


def test_mislukte_run_blijft_zichtbaar(tmp_path: Path) -> None:
    """Een run die faalde op een ontbrekende credential is auditinformatie."""
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))
    runs_mod.registreer(
        d,
        door="a@conduction.nl",
        modus="live",
        norm="9001",
        bronnen=["jira"],
        fout="JIRA_API_TOKEN ontbreekt",
    )
    (rec,) = runs_mod.lijst(d)
    assert rec["status"] == "fout"
    assert "JIRA_API_TOKEN" in rec["fout"]


def test_nieuwe_audit_is_zelfstandig_compleet(tmp_path: Path) -> None:
    """Een audit moet vanaf het aanmaken een live run kunnen afronden.

    Gemeten op 2026-08-16: `memo-input.yaml` ontbrak, waardoor een run die alle zeven
    pipelinestappen én alle rapporten met succes had afgerond, alsnog als `fout` in de
    trail belandde — met `0 toegevoegd`, terwijl er 87 bevindingen waren geland.
    """
    import yaml

    from iso_audit.api.registry import FINDINGS, MANIFEST, MEMO_INPUT
    from iso_audit.memo.models import MemoInput

    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))

    for bestand in (MANIFEST, FINDINGS, MEMO_INPUT):
        assert (d / bestand).is_file(), f"{bestand} ontbreekt in een verse audit"

    # En geldig volgens het model, niet alleen aanwezig: een kapotte steiger faalt pas
    # bij het renderen, en dat is te laat.
    MemoInput(**yaml.safe_load((d / MEMO_INPUT).read_text(encoding="utf-8")))


def test_memo_input_neemt_de_scope_van_de_audit_over(tmp_path: Path) -> None:
    import yaml

    from iso_audit.api.registry import MEMO_INPUT

    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001", "27001"], periode="2026-H2", door="a@c.nl"))
    data = yaml.safe_load((d / MEMO_INPUT).read_text(encoding="utf-8"))

    assert data["cycle"] == "2026-H2"
    assert set(data["context"]["scope"]) == {"ISO 9001:2015", "ISO 27001:2022"}


def test_geraadpleegde_bronnen_over_runs_heen(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))
    # Een run heeft twee records: een start (`loopt`) en een afsluiting. Alleen afgeronde
    # runs tellen mee — een run die faalde heeft niets geraadpleegd.
    een = runs_mod.registreer(d, door="a@c.nl", modus="sim", norm="9001", bronnen=["drive"])
    runs_mod.afsluiten(d, str(een["run_id"]))
    twee = runs_mod.registreer(
        d, door="a@c.nl", modus="sim", norm="9001", bronnen=["jira", "drive"]
    )
    runs_mod.afsluiten(d, str(twee["run_id"]))
    assert runs_mod.geraadpleegde_bronnen(d) == ["drive", "jira"]


def test_een_lopende_of_mislukte_run_telt_niet_als_geraadpleegd(tmp_path: Path) -> None:
    """De kolom "Bronnen" is een bewijsuitspraak, geen intentie."""
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))

    runs_mod.registreer(d, door="a@c.nl", modus="live", norm="9001", bronnen=["drive"])
    assert runs_mod.geraadpleegde_bronnen(d) == [], "lopende run telt nog niet mee"

    mislukt = runs_mod.registreer(d, door="a@c.nl", modus="live", norm="9001", bronnen=["jira"])
    runs_mod.afsluiten(d, str(mislukt["run_id"]), fout="credential geweigerd")
    assert runs_mod.geraadpleegde_bronnen(d) == [], "mislukte run heeft niets gelezen"

    assert runs_mod.som(d) == 2, "twee runs, ook al zijn er drie records"


# --- gelijktijdigheid ----------------------------------------------------


def test_andere_actief_waarschuwt_maar_blokkeert_niet(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")

    r.markeer_actief(aid, "a@conduction.nl")
    assert r.andere_actief(aid, "a@conduction.nl") is None, "eigen activiteit is geen waarschuwing"

    waarschuwing = r.andere_actief(aid, "b@conduction.nl")
    assert waarschuwing is not None
    assert waarschuwing["identiteit"] == "a@conduction.nl"


def test_oude_activiteit_waarschuwt_niet(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")
    (r.pad(aid) / ".actief").write_text(
        json.dumps({"identiteit": "a@conduction.nl", "ts": "2020-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    assert r.andere_actief(aid, "b@conduction.nl") is None


# --- overzicht -----------------------------------------------------------


def test_status_nieuw_zonder_run(tmp_path: Path) -> None:
    """Een aangemaakte audit zonder run is een geldige toestand en moet zichtbaar zijn."""
    r = AuditRegistry(tmp_path)
    r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")
    (regel,) = ov.alles(r)
    assert regel.status == ov.STATUS_NIEUW
    assert regel.runs == 0


def test_status_loopt_en_memo_klaar(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl")
    d = r.pad(aid)
    runs_mod.voeg_toe(d, [_kandidaat(id="f1")])
    runs_mod.registreer(d, door="a@c.nl", modus="sim", norm="9001", bronnen=["drive"])
    assert ov.regel(d).status == ov.STATUS_LOOPT

    data = json.loads((d / "findings.json").read_text(encoding="utf-8"))
    data[0]["triage_status"] = "valide"
    (d / "findings.json").write_text(json.dumps(data), encoding="utf-8")
    (d / ov.MEMO_BESTAND).write_text("pdf", encoding="utf-8")
    assert ov.regel(d).status == ov.STATUS_MEMO_KLAAR


def test_overzicht_toont_laatste_actor_uit_de_trail(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    d = r.pad(r.maak(normen=["9001"], periode="2026-Q3", door="a@conduction.nl"))
    with (d / "triage_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"timestamp": "2026-08-01T10:00:00Z", "actor": "eerste@c.nl"}) + "\n")
        fh.write(json.dumps({"timestamp": "2026-08-02T11:00:00Z", "actor": "laatste@c.nl"}) + "\n")

    regel = ov.regel(d)
    assert regel.laatste_actor == "laatste@c.nl"
    assert regel.laatste_wijziging == "2026-08-02T11:00:00Z"


def test_overzicht_sorteert_nieuwste_periode_eerst(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    r.maak(normen=["9001"], periode="2026-Q1", door="a@c.nl")
    r.maak(normen=["9001"], periode="2026-Q3", door="a@c.nl")
    r.maak(normen=["27001"], periode="2026-Q2", door="a@c.nl")
    assert [x.periode for x in ov.alles(r)] == ["2026-Q3", "2026-Q2", "2026-Q1"]


def test_overzicht_negeert_losse_mappen(tmp_path: Path) -> None:
    """Een directory zonder manifest is geen audit — niet meetellen."""
    r = AuditRegistry(tmp_path)
    r.maak(normen=["9001"], periode="2026-Q3", door="a@c.nl")
    (tmp_path / "rommel").mkdir()
    assert len(ov.alles(r)) == 1


def test_overzicht_op_lege_root(tmp_path: Path) -> None:
    assert ov.alles(AuditRegistry(tmp_path / "bestaat-niet")) == []


# --- meerdere normen per audit -------------------------------------------


def test_audit_over_beide_normen(tmp_path: Path) -> None:
    """9001 én 27001 is één audit met één memo, geen twee administraties."""
    r = AuditRegistry(tmp_path)
    aid = r.maak(normen=["9001", "27001"], periode="2026-Q3", door="a@c.nl")
    assert aid == "27001_9001-2026-Q3"

    manifest = json.loads((r.pad(aid) / "audit.json").read_text(encoding="utf-8"))
    assert manifest["normen"] == ["27001", "9001"]


def test_norm_db_slug_wordt_korte_code() -> None:
    """De UI mag norm-DB-slugs sturen; er is één vocabulaire."""
    from iso_audit.api.registry import norm_code

    assert norm_code("iso-9001-2015") == "9001"
    assert norm_code("iso-27001-2022") == "27001"
    assert norm_code("9001") == "9001"


def test_slug_en_code_leveren_hetzelfde_id(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    assert audit_id(["iso-9001-2015"], "2026-Q3") == audit_id(["9001"], "2026-Q3")
    r.maak(normen=["iso-9001-2015"], periode="2026-Q3", door="a@c.nl")
    with pytest.raises(RegistryError, match="bestaat al"):
        r.maak(normen=["9001"], periode="2026-Q3", door="a@c.nl")


def test_run_code_leidt_de_pipeline_parameter_af() -> None:
    from iso_audit.api.registry import run_code

    assert run_code(["9001"]) == "9001"
    assert run_code(["27001"]) == "27001"
    assert run_code(["9001", "27001"]) == "beide"
    assert run_code(["iso-27001-2022", "iso-9001-2015"]) == "beide"


def test_norm_die_de_pipeline_niet_kent_faalt_hard(tmp_path: Path) -> None:
    """Kiesbaar in de norm-DB is niet hetzelfde als draaibaar.

    De norm-keuze staat op vier plekken in de pipeline hardcoded. Een derde norm mag
    dus niet stil de verkeerde run opleveren — hij faalt bij het aanmaken.
    """
    r = AuditRegistry(tmp_path)
    with pytest.raises(RegistryError, match="nog niet draaien"):
        r.maak(normen=["iso-14001-2015"], periode="2026-Q3", door="a@c.nl")
    assert list(tmp_path.iterdir()) == []


def test_lege_normlijst_faalt(tmp_path: Path) -> None:
    r = AuditRegistry(tmp_path)
    with pytest.raises(RegistryError, match="minstens één norm"):
        r.maak(normen=[], periode="2026-Q3", door="a@c.nl")
