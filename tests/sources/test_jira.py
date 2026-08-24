"""Tests voor `iso_audit.sources.jira.JiraSource` (§3.4.4)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from iso_audit.sources.base import Document, Source

# De JIRA_*-env wordt repo-breed schoongemaakt door `_schone_omgeving` in
# `tests/conftest.py`. Die fixture stond hier eerst lokaal; ze is verplaatst toen bleek dat
# `test_pipeline_ingest.py` dezelfde bescherming nodig had en niet had.


def _fake_response(ok: bool = True, status: int = 200, data: dict[str, Any] | None = None) -> Any:
    m = MagicMock()
    m.ok = ok
    m.status_code = status
    m.text = "" if ok else "error"
    m.json.return_value = data or {}
    return m


def _issue(key: str, summary: str, labels: list[str] | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "updated": "2026-05-01T10:00:00.000+0000",
            "labels": labels or [],
            "description": {"content": [{"type": "paragraph", "content": [{"text": "Body"}]}]},
        },
    }


# ---------- healthcheck ----------


def test_healthcheck_zonder_creds_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    h = JiraSource().healthcheck()
    assert h["status"] == "fail"


def test_healthcheck_met_creds_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    notif = JiraSource(
        base_url="https://co.atlassian.net",
        email="a@b",
        api_token="tkn",
    )
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data={"displayName": "Mark"}),
    ):
        h = notif.healthcheck()
    assert h["status"] == "ok"
    assert h["user"] == "Mark"


def test_scoped_token_gebruikt_bearer_en_de_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    """Atlassian kent twee tokensoorten en ze werken verschillend.

    Gemeten op 2026-08-15 met een echt service-token: Basic auth op de site-URL gaf 401,
    Bearer op de site-URL gaf 403 op élk endpoint (ook `serverInfo`), en Bearer op
    `api.atlassian.com/ex/jira/{cloudId}` gaf 200. Zonder dit onderscheid is een
    Jira-koppeling zonder persoonsgebonden account niet mogelijk.
    """
    from iso_audit.sources.jira import JiraSource

    bron = JiraSource(base_url="https://x.atlassian.net", api_token="ATSTT3xxxx", email="")
    assert bron.scoped is True

    gezien: dict[str, object] = {}

    def _nep_get(url: str, **kw: object) -> object:
        gezien.setdefault("urls", []).append(url)  # type: ignore[union-attr]
        gezien["headers"] = kw.get("headers")
        gezien["auth"] = kw.get("auth")
        if url.endswith("/_edge/tenant_info"):
            return _fake_response(data={"cloudId": "wolk-123"})
        return _fake_response(data={"displayName": "Iso-tool"})

    with patch("iso_audit.sources.jira.requests.get", side_effect=_nep_get):
        h = bron.healthcheck()

    assert h["status"] == "ok"
    urls = gezien["urls"]
    assert urls[0].endswith("/_edge/tenant_info"), "cloud-ID eerst ophalen"
    assert urls[1] == "https://api.atlassian.com/ex/jira/wolk-123/rest/api/3/myself"
    assert gezien["headers"]["Authorization"] == "Bearer ATSTT3xxxx"  # type: ignore[index]
    assert gezien["auth"] is None, "geen Basic auth bij een scoped token"


def test_scoped_token_vraagt_geen_e_mailadres(monkeypatch: pytest.MonkeyPatch) -> None:
    """Een e-mailadres is alleen de gebruikersnaam voor Basic auth met een persoonlijk
    token. Het verplicht stellen zou vragen om een persoonsgebonden gegeven dat deze
    koppeling juist niet mag hebben."""
    from iso_audit.sources.jira import JiraSource

    bron = JiraSource(base_url="https://x.atlassian.net", api_token="ATSTT3xxxx", email="")
    with patch("iso_audit.sources.jira.requests.get", side_effect=OSError("niet gebeld")):
        h = bron.healthcheck()
    # Faalt op het netwerk, niet op ontbrekende configuratie.
    assert h["soort"] != "niet_geconfigureerd"

    zonder_token = JiraSource(base_url="https://x.atlassian.net", api_token="", email="")
    assert zonder_token.healthcheck()["soort"] == "niet_geconfigureerd"


def test_gebruikerstoken_blijft_basic_auth_op_de_site_url() -> None:
    """Geen stille breaking change voor een bestaande `ATATT`-configuratie."""
    from iso_audit.sources.jira import JiraSource

    bron = JiraSource(base_url="https://x.atlassian.net", api_token="ATATTxxxx", email="a@b.nl")
    assert bron.scoped is False

    gezien: dict[str, object] = {}

    def _nep_get(url: str, **kw: object) -> object:
        gezien["url"] = url
        gezien["auth"] = kw.get("auth")
        gezien["headers"] = kw.get("headers")
        return _fake_response(data={"displayName": "Iemand"})

    with patch("iso_audit.sources.jira.requests.get", side_effect=_nep_get):
        bron.healthcheck()

    assert gezien["url"] == "https://x.atlassian.net/rest/api/3/myself"
    assert gezien["auth"] == ("a@b.nl", "ATATTxxxx")
    assert "Authorization" not in gezien["headers"]  # type: ignore[operator]


def test_healthcheck_api_fail_geeft_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    notif = JiraSource(base_url="https://x", email="a@b", api_token="t")
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(ok=False, status=401),
    ):
        h = notif.healthcheck()
    assert h["status"] == "fail"
    # `_http_get` bouwt zijn fout als "Jira API {code} op {url}: {resp.text}". Die tekst
    # asserteerde deze test eerder ("401" moest erin staan) en legde daarmee het lek vast
    # als gewenst gedrag: tenant-URL en responsbody bereikten de browser. De soort draagt
    # de betekenis nu, de ruwe melding gaat naar het serverlog.
    assert h["soort"] == "auth"
    assert "401" not in str(h["reden"])
    assert "https://" not in str(h["reden"])


# ---------- list_documents ----------


def test_list_documents_pagineert(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t", page_size=2)
    # Enhanced search: token-pagination via nextPageToken; laatste pagina isLast.
    page1 = {
        "issues": [_issue("AUD-1", "Eerste"), _issue("AUD-2", "Tweede")],
        "nextPageToken": "tok2",
    }
    page2 = {"issues": [_issue("AUD-3", "Derde")], "isLast": True}
    with patch(
        "iso_audit.sources.jira.requests.get",
        side_effect=[_fake_response(data=page1), _fake_response(data=page2)],
    ) as mock_get:
        docs = list(src.list_documents())
    assert [d.id for d in docs] == ["AUD-1", "AUD-2", "AUD-3"]
    assert mock_get.call_count == 2
    # Tweede call moet de paginatie-token meesturen.
    assert mock_get.call_args.kwargs["params"]["nextPageToken"] == "tok2"


def test_list_documents_geeft_document_velden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t")
    page = {"issues": [_issue("AUD-1", "Titel A")], "total": 1}
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data=page),
    ):
        docs = list(src.list_documents())
    assert docs[0].titel == "Titel A"
    assert docs[0].bron == "jira"
    assert docs[0].type == "issue"
    assert docs[0].inhoud_uri.startswith("jira://")


def test_list_documents_zonder_base_url_geeft_lege_iterator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Een Source zonder config raakt nooit de API en doet niets."""
    from iso_audit.sources.jira import JiraSource

    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    src = JiraSource()
    docs = list(src.list_documents())
    assert docs == []


def test_list_documents_filter_overschrijft_default_jql(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t", default_jql="project=A")
    page = {"issues": [], "total": 0}
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data=page),
    ) as mock_get:
        list(src.list_documents(filter={"jql": "labels=iso27001"}))
    used_jql = mock_get.call_args.kwargs["params"]["jql"]
    assert used_jql == "labels=iso27001"


# ---------- fetch_content ----------


def test_fetch_content_render_adf(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t")
    issue_data = {
        "fields": {
            "description": {
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"text": "Eerste paragraaf"}],
                    }
                ]
            },
            "comment": {
                "comments": [
                    {
                        "body": {
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"text": "Commentaar"}],
                                }
                            ]
                        }
                    }
                ]
            },
        }
    }
    doc = Document(
        id="AUD-1",
        titel="t",
        bron="jira",
        type="issue",
        laatst_gewijzigd="2026-05-01T10:00:00Z",
        inhoud_uri="jira://AUD-1",
    )
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data=issue_data),
    ):
        body = src.fetch_content(doc)
    assert "Eerste paragraaf" in body
    assert "Commentaar" in body


# ---------- list_findings ----------


def test_list_findings_emit_findings_met_clausule_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t")
    monkeypatch.delenv("JIRA_FINDINGS_JQL", raising=False)
    page = {
        "issues": [
            _issue("AUD-1", "Backup procedure", labels=["iso27001-5.30"]),
            _issue("AUD-2", "Generieke vraag", labels=["compliance"]),
        ],
        "total": 2,
    }
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data=page),
    ):
        findings = list(src.list_findings("sessie-1"))
    assert len(findings) == 2
    assert findings[0].clausule_ids == ["5.30"]
    # 'compliance' wordt niet naar een clausule-id gemapt; lege lijst.
    assert findings[1].clausule_ids == []
    # Het id is de Jira-sleutel en niet `sessie-1:<key>`. Die prefix stond hier tot
    # 2026-08-24 en maakte elk opvolgpunt per run uniek: drie runs op één database gaven 83
    # sleutels 249 rijen, zonder ook maar één modelaanroep. Zie
    # `tests/sources/test_jira_opvolgpunt_id.py` voor de meting.
    assert findings[0].id == "AUD-1"


def test_list_findings_iso9001_label(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t")
    monkeypatch.delenv("JIRA_FINDINGS_JQL", raising=False)
    page = {
        "issues": [_issue("AUD-9", "y", labels=["iso9001-9.1"])],
        "total": 1,
    }
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data=page),
    ):
        findings = list(src.list_findings("sessie-9"))
    assert findings[0].clausule_ids == ["9.1"]


# ---------- protocol + registry ----------


def test_jira_implementeert_source_protocol() -> None:
    from iso_audit.sources.jira import JiraSource

    assert isinstance(JiraSource(), Source)


def test_jira_geregistreerd_in_sources() -> None:
    import iso_audit.sources.jira  # noqa: F401
    from iso_audit import sources

    assert "jira" in sources.available()


# ---------- HTTP-error path ----------


def test_http_get_error_raised_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(base_url="https://x", email="e@b", api_token="t")
    with (
        patch(
            "iso_audit.sources.jira.requests.get",
            return_value=_fake_response(ok=False, status=500),
        ),
        pytest.raises(OSError, match="500"),
    ):
        list(src.list_documents())


# ---------- JIRA_USER_EMAIL + JIRA_PROJECTS scoping ----------


def test_email_uit_jira_user_email(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    monkeypatch.setenv("JIRA_USER_EMAIL", "user@conduction.nl")
    monkeypatch.setenv("JIRA_EMAIL", "old@conduction.nl")  # mag JIRA_USER_EMAIL niet overrulen
    assert JiraSource()._email == "user@conduction.nl"


def test_email_fallback_naar_jira_email(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    monkeypatch.setenv("JIRA_EMAIL", "old@conduction.nl")  # JIRA_USER_EMAIL afwezig
    assert JiraSource()._email == "old@conduction.nl"


def test_jira_projects_scopt_jql(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    monkeypatch.setenv("JIRA_PROJECTS", "ISO, COMP")
    src = JiraSource(
        base_url="https://x", email="e@b", api_token="t", default_jql="labels=iso27001"
    )
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data={"issues": [], "total": 0}),
    ) as mock_get:
        list(src.list_documents())
    used = mock_get.call_args.kwargs["params"]["jql"]
    assert used == '(project in ("ISO", "COMP")) AND (labels=iso27001)'


def test_jira_projects_scope_zonder_base_jql(monkeypatch: pytest.MonkeyPatch) -> None:
    from iso_audit.sources.jira import JiraSource

    monkeypatch.setenv("JIRA_PROJECTS", "ISO")
    src = JiraSource(base_url="https://x", email="e@b", api_token="t")  # geen default_jql
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data={"issues": [], "total": 0}),
    ) as mock_get:
        list(src.list_documents())
    assert mock_get.call_args.kwargs["params"]["jql"] == 'project in ("ISO")'


def test_geen_jira_projects_laat_jql_ongemoeid() -> None:
    from iso_audit.sources.jira import JiraSource

    src = JiraSource(
        base_url="https://x", email="e@b", api_token="t", default_jql="labels=iso27001"
    )
    with patch(
        "iso_audit.sources.jira.requests.get",
        return_value=_fake_response(data={"issues": [], "total": 0}),
    ) as mock_get:
        list(src.list_documents())
    assert mock_get.call_args.kwargs["params"]["jql"] == "labels=iso27001"
