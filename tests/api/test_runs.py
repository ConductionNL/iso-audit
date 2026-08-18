"""Tests voor `api/runs.py` — het append-only run-record.

Waarom een eigen bestand: het run-record is de audittrail van een run, en de garantie is dat
er alleen wordt toegevoegd. Wat erin hoort te staan — en met welke context een getal
navertelbaar is — is daarmee zelf een contract.
"""

from __future__ import annotations

from pathlib import Path

from iso_audit.api import runs

# --- kosten in het afsluitrecord -------------------------------------------


def test_afsluiten_zet_kosten_met_peildatum_en_grondslag(tmp_path: Path) -> None:
    """Een bedrag zonder peildatum en grondslag is niet navertelbaar.

    Tot 2026-08-17 stond het kostenbedrag alleen in het log, terwijl de rest van de
    runhistorie wél in de trail zat. Een auditor die later vroeg wat een run kostte, moest
    door logs zoeken. En zonder grondslag is het bedrag niet te interpreteren: lijstprijs is
    niet hetzelfde als wat er gefactureerd wordt.
    """
    from iso_audit.api.runs import Kosten

    runs.registreer(tmp_path, door="a@b.c", modus="live", norm="27001", bronnen=["drive"])
    runs.afsluiten(
        tmp_path,
        "run-0001",
        toegevoegd=3,
        kosten=Kosten(
            usd=0.7893,
            model="claude-haiku-4-5",
            peildatum="2026-08-14",
            grondslag="lijstprijs",
            calls=215,
        ),
    )
    laatste = runs.samengevat(tmp_path)[-1]
    k = laatste["kosten"]
    assert k["usd"] == 0.7893
    assert k["model"] == "claude-haiku-4-5"
    assert k["peildatum"] == "2026-08-14"
    assert k["grondslag"] == "lijstprijs", "zonder grondslag is het bedrag niet te lezen"
    assert k["calls"] == 215


def test_afsluiten_zonder_kosten_laat_het_veld_weg(tmp_path: Path) -> None:
    """Een ingest-only run raakt de API niet; nul rapporteren zou classificatie suggereren."""
    runs.registreer(tmp_path, door="a@b.c", modus="live", norm="27001", bronnen=["drive"])
    runs.afsluiten(tmp_path, "run-0001", toegevoegd=1)
    assert "kosten" not in runs.samengevat(tmp_path)[-1]


# --- dekking in het afsluitrecord ------------------------------------------


def test_afsluiten_zet_dekking_met_redenen(tmp_path: Path) -> None:
    """Het aantal documenten zonder de dekking is een dekkingsclaim die niemand kan nagaan.

    Gemeten op 2026-08-17: 512 bestanden in de bron, 299 gelezen. Een auditor die 299
    documenten zag, zag niet dat er 213 buiten stonden — dat stond alleen in een logregel die
    een podherstart niet overleeft.
    """
    from iso_audit.api.runs import Dekking

    runs.registreer(tmp_path, door="a@b.c", modus="live", norm="27001", bronnen=["drive"])
    runs.afsluiten(
        tmp_path,
        "run-0001",
        toegevoegd=3,
        dekking=Dekking(
            gezien=512,
            gelezen=299,
            overgeslagen={"image/png: afbeelding": 121, "onbekend type: video/mp4": 92},
        ),
    )
    d = runs.samengevat(tmp_path)[-1]["dekking"]
    assert d["gezien"] == 512
    assert d["gelezen"] == 299
    assert d["niet_gelezen"] == 213, "het totaal moet uit de redenen volgen, niet los geteld"
    assert d["overgeslagen"]["image/png: afbeelding"] == 121


def test_dekking_bevat_geen_bestandsnamen(tmp_path: Path) -> None:
    """Aantallen per reden, geen namen: 213 namen per record maakt de trail onleesbaar."""
    from iso_audit.api.runs import Dekking

    record = Dekking(gezien=2, gelezen=1, overgeslagen={"onbekend type: video/mp4": 1}).als_record()
    assert set(record) == {"gezien", "gelezen", "niet_gelezen", "overgeslagen"}


def test_afsluiten_zonder_dekking_laat_het_veld_weg(tmp_path: Path) -> None:
    """Een run zonder Drive leest geen bestanden; een dekking van 0/0 zou misleiden."""
    runs.registreer(tmp_path, door="a@b.c", modus="live", norm="27001", bronnen=["jira"])
    runs.afsluiten(tmp_path, "run-0001", toegevoegd=1)
    assert "dekking" not in runs.samengevat(tmp_path)[-1]
