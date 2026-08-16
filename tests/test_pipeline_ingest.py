"""Ingest als eigen stap: vastleggen wat je las, en niet stil doen alsof het lukte.

Twee dingen die op 2026-08-15 met een echte run zijn gemeten en hier zijn vastgelegd:

1. `run_audit` hield alles in het geheugen en schreef pas ná de classificatie iets weg. Een
   run die op een ontbrekende API-key strandde gooide daarmee 149 documenten en
   tweeënhalve minuut Drive-lezen volledig weg.
2. Een bron die tijdens de ingest faalde werd afgevangen met een logregel, waarna de run
   `klaar` meldde. Gemeten geval: Jira gaf HTTP 400 ("Unbounded JQL queries are not allowed
   here") en leverde nul documenten, terwijl de auditor hem expliciet had gekozen.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from iso_audit import pipeline


def _doc(doc_id: str, naam: str) -> dict[str, Any]:
    return {"id": doc_id, "naam": naam, "tekst": "inhoud", "herkomst": "Drive"}


@pytest.fixture(autouse=True)
def _eigen_db(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "audit.db"))


def _tel(tabel: str, monkeypatch_pad: str) -> int:
    import sqlite3

    conn = sqlite3.connect(monkeypatch_pad)
    try:
        return int(conn.execute(f"select count(*) from {tabel}").fetchone()[0])
    finally:
        conn.close()


def test_ingest_legt_vast_zonder_classificatie(tmp_path: Any) -> None:
    """`alleen_ingest` raakt de Claude-API niet en bewaart wél wat het las."""
    docs = [_doc("d1", "Beleid.docx"), _doc("d2", "Procedure.docx")]

    with (
        patch.object(pipeline, "_valideer_env"),
        patch("iso_audit.sources.drive.haal_documenten_op", return_value=(docs, [])),
        patch("iso_audit.classification.findings.classificeer_alle_bevindingen") as classificeer,
    ):
        pipeline.run_audit("9001", sources=["drive"], alleen_ingest=True, no_review=True)

    assert not classificeer.called, "alleen-ingest mag de classificatie niet aanroepen"
    assert _tel("documents", str(tmp_path / "audit.db")) == 2


def test_een_mislukte_bron_maakt_de_run_niet_stil_klaar(tmp_path: Any) -> None:
    """Doorgaan is juist — één kapotte bron mag een audit niet stilleggen — maar de run
    mag daarna niet `klaar` melden alsof er niets aan de hand was."""
    docs = [_doc("d1", "Beleid.docx")]

    with (
        patch.object(pipeline, "_valideer_env"),
        patch("iso_audit.sources.drive.haal_documenten_op", return_value=(docs, [])),
        patch(
            "iso_audit.sources.opvolgpunten.haal_op",
            side_effect=OSError("Jira API 400 op https://tenant/rest: unbounded"),
        ),
        pytest.raises(pipeline.BronIngestError) as fout,
    ):
        pipeline.run_audit("9001", sources=["drive", "jira"], alleen_ingest=True, no_review=True)

    assert "jira" in fout.value.bronnen
    # De ruwe leveranciersmelding hoort in het serverlog, niet in het run-record.
    assert "tenant" not in str(fout.value)
    assert "400" not in str(fout.value)
    # En wat Drive wél opleverde is bewaard: de fout van de ene bron mag het werk van de
    # andere niet weggooien.
    assert _tel("documents", str(tmp_path / "audit.db")) == 1


def test_jira_zonder_scope_stuurt_geen_lege_query() -> None:
    """Jira Cloud weigert een onbegrensde query met HTTP 400; dat leverde stil nul
    documenten op bij een gekozen en gekoppelde bron."""
    from iso_audit.sources.jira import JiraSource

    bron = JiraSource(base_url="https://x", email="a@b", api_token="t")
    assert bron._scope_jql("").strip() != ""
    assert "updated" in bron._scope_jql("")

    # Met een eigen JQL of projectscope blijft die leidend.
    assert bron._scope_jql("status = Open") == "status = Open"
