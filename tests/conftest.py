"""Gedeelde fixtures voor contract-tests.

Doel: één fixture-set die door zowel Source- als Notifier-contract-tests wordt
geconsumeerd. Adapters worden parametrized getest tegen deze fixtures, zodat
elke nieuwe adapter automatisch dezelfde invarianten krijgt te valideren als
de eerste.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from iso_audit.modes.base import Decision
from iso_audit.sources.base import Document, Finding


@pytest.fixture(autouse=True)
def _geen_impersonation_uit_de_omgeving(monkeypatch: pytest.MonkeyPatch) -> None:
    """Maak de suite onafhankelijk van `GWS_IMPERSONATE_EMAIL` op de machine.

    Staat die variabele gevuld — en op een werkstation dat het portaal lokaal draait staat
    hij dat — dan bouwt `auth.get_credentials()` gedelegeerde credentials in plaats van
    gewone, en falen 9 tests in `test_auth.py`. Gemeten op 2026-08-16: 9 failed, 11 passed
    met de variabele gezet; groen zonder.

    Autouse en repo-breed, niet per test: het raakt elke test die credentials bouwt, en een
    test die eraan moet dénken zichzelf te isoleren vergeet het uiteindelijk. Zie de
    testisolatie-regel in `~/.claude/CLAUDE.md`.
    """
    monkeypatch.delenv("GWS_IMPERSONATE_EMAIL", raising=False)


@pytest.fixture
def sample_document() -> Document:
    """Een geldig Document-instance voor adapter-conformance tests."""
    return Document(
        id="fixture-doc-1",
        titel="Beleid Informatiebeveiliging",
        bron="fixture",
        type="beleid",
        laatst_gewijzigd="2026-04-01T00:00:00Z",
        inhoud_uri="fixture://doc-1",
    )


@pytest.fixture
def sample_documents() -> list[Document]:
    """Een kleine set documenten voor list-iteration tests."""
    return [
        Document(
            id="fixture-doc-1",
            titel="Beleid Informatiebeveiliging",
            bron="fixture",
            type="beleid",
            laatst_gewijzigd="2026-04-01T00:00:00Z",
            inhoud_uri="fixture://doc-1",
        ),
        Document(
            id="fixture-doc-2",
            titel="Procedure Toegangsbeheer",
            bron="fixture",
            type="procedure",
            laatst_gewijzigd="2026-03-15T00:00:00Z",
            inhoud_uri="fixture://doc-2",
        ),
    ]


@pytest.fixture
def sample_finding() -> Finding:
    """Een geldig Finding-instance."""
    return Finding(
        id="fixture-finding-1",
        bron="fixture",
        clausule_ids=["5.1", "8.16"],
        omschrijving="Voorbeeld-bevinding voor contract-tests",
        bewijs_uris=["fixture://doc-1"],
    )


@pytest.fixture
def sample_decision() -> Decision:
    """Een geldig Decision-instance voor Notifier-contract-tests."""
    return Decision(
        punt="classify_finding",
        context={"document_id": "fixture-doc-1", "norm": "27001"},
        voorstel={"klasse": "OFI", "clausule": "8.16"},
        risico="midden",
        audit_id="fixture-audit-2026-q1",
    )


@pytest.fixture
def lege_registries() -> Iterator[None]:
    """Reset alle protocol-registries vóór en ná elke test die deze fixture gebruikt.

    Voorkomt dat tests elkaar besmetten via globale registry-state. Na de
    test worden de bundled adapters opnieuw geregistreerd door hun modules
    te re-importeren — anders zou daarop-volgend testorder breken voor
    tests die `available()`/`get()` direct gebruiken.
    """
    import importlib
    import sys

    from iso_audit.notifiers import _reset_for_tests as _reset_notifiers
    from iso_audit.sinks import _reset_for_tests as _reset_sinks
    from iso_audit.sources import _reset_for_tests as _reset_sources

    _reset_sources()
    _reset_sinks()
    _reset_notifiers()
    yield
    _reset_sources()
    _reset_sinks()
    _reset_notifiers()

    # Re-registreer bundled adapters. Als de module al in sys.modules zit,
    # `reload()` om de @register-decorator opnieuw te triggeren. Anders
    # `import_module()` — dat voert het module-script éénmaal uit.
    # `reload()` na vers `import_module()` zou de decorator twee keer
    # uitvoeren en in dubbele-registratie eindigen.
    for mod_naam in (
        "iso_audit.sources.drive",
        "iso_audit.sources.planning",
        "iso_audit.sources.jira",
        "iso_audit.notifiers.slack",
        "iso_audit.notifiers.email",
        "iso_audit.sinks.drive",
    ):
        try:
            if mod_naam in sys.modules:
                importlib.reload(sys.modules[mod_naam])
            else:
                importlib.import_module(mod_naam)
        except ImportError:
            continue
