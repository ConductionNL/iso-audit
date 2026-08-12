"""Gedeelde testhelpers voor het audit-gescopede portaal (change portal-dashboard).

De API is per change `portal-dashboard` audit-gescoped: `/audits/{id}/findings` in
plaats van `/findings`. Om te voorkomen dat elke bestaande test dat pad moet
herhalen, zet `PortaalClient` de prefix erop — behalve voor de routes die bewust
audit-onafhankelijk zijn.

Die uitzonderingenlijst staat hier expliciet en niet als slimme regel: `/healthz`
hoort buiten de auth-gate én buiten elke audit, en `/config/*` beschrijft de
omgeving. Een test die per ongeluk `/audits/x/healthz` aanroept zou een groen
resultaat kunnen geven op een route die in productie niet bestaat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient

from iso_audit.api.app import create_app
from iso_audit.api.registry import AuditRegistry

EXAMPLES = Path("examples/auditmemo")
NORMS = "examples/norms"
AUDITOR = "auditor@conduction.nl"

ONGESCOPED = ("/healthz", "/config", "/audits", "/openapi.json", "/docs")
"""Paden die niet onder een audit vallen; al het andere krijgt de audit-prefix.

`"/"` staat hier **niet** in: elk pad begint ermee, dus `startswith` zou dan altijd
waar zijn en niets zou geprefixt worden. De root wordt apart afgehandeld."""


class PortaalClient:
    """TestClient-wrapper die audit-relatieve paden prefixt.

    ``client.get("/findings")`` wordt ``/audits/<aid>/findings``. Gebruik
    ``client.raw`` voor de onderliggende client wanneer je expliciet een volledig
    pad wil.
    """

    def __init__(self, client: TestClient, audit_id: str, audit_dir: Path) -> None:
        self.raw = client
        self.audit_id = audit_id
        self.audit_dir = audit_dir
        """Directory van deze audit, voor tests die de bestanden direct inspecteren."""

    def _pad(self, pad: str) -> str:
        if pad == "/" or pad.startswith(ONGESCOPED):
            return pad
        return f"/audits/{self.audit_id}{pad}"

    def get(self, pad: str, **kw: Any) -> httpx.Response:
        return self.raw.get(self._pad(pad), **kw)

    def post(self, pad: str, **kw: Any) -> httpx.Response:
        return self.raw.post(self._pad(pad), **kw)


def maak_portaal(
    tmp_path: Path,
    *,
    findings: list[dict[str, Any]] | None = None,
    norm: str = "9001",
    periode: str = "2026-Q3",
    memo_input: Path | None = None,
    headers: dict[str, str] | None = None,
) -> PortaalClient:
    """Bouw een portaal met één audit erin en geef een client op die audit.

    ``memo_input`` laat een test een schrijfbare kopie meegeven; standaard wordt het
    voorbeeld uit `examples/auditmemo` gekopieerd zodat de memo-routes werken zonder
    dat een test het bronbestand muteert.
    """
    root = tmp_path / "audits"
    registry = AuditRegistry(root)
    aid = registry.maak(norm=norm, periode=periode, door=AUDITOR)
    audit_dir = registry.pad(aid)

    if findings is not None:
        (audit_dir / "findings.json").write_text(
            json.dumps(findings, ensure_ascii=False), encoding="utf-8"
        )

    bron = memo_input or (EXAMPLES / "memo-input.yaml")
    (audit_dir / "memo-input.yaml").write_text(bron.read_text(encoding="utf-8"), encoding="utf-8")

    app = create_app(
        registry,
        profile=str(EXAMPLES / "conduction.profile.yaml"),
        norms_dir=NORMS,
    )
    # `headers={}` betekent bewust GEEN identity-header (fail-closed-tests);
    # alleen `None` valt terug op de auditor-default.
    standaard = {"X-Forwarded-Email": AUDITOR}
    client = TestClient(app, headers=standaard if headers is None else headers)
    return PortaalClient(client, aid, audit_dir)
