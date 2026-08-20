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

# Variabelen die de uitkomst van een test veranderen zonder dat de test ze noemt. Twee
# bronnen: de `.env` van de machine (via `load_dotenv()` bij import) en andere tests —
# `BronConfig.naar_omgeving()` schrijft opgeslagen configuratie in `os.environ`, en die
# blijft daarna staan voor de rest van de sessie.
_OMGEVING_DIE_TESTS_BEINVLOEDT: tuple[str, ...] = (
    # Gedelegeerde i.p.v. gewone credentials in `auth.get_credentials()`.
    "GWS_IMPERSONATE_EMAIL",
    # Veranderen de JQL die adapters opbouwen, en daarmee de assertions erop.
    "JIRA_BASE_URL",
    "JIRA_USER_EMAIL",
    "JIRA_EMAIL",
    "JIRA_API_TOKEN",
    "JIRA_JQL",
    "JIRA_FINDINGS_JQL",
    "JIRA_PROJECTS",
)


@pytest.fixture(autouse=True)
def _schone_omgeving(monkeypatch: pytest.MonkeyPatch) -> None:
    """Maak elke test onafhankelijk van omgevingsvariabelen die hij niet zelf zet.

    Twee gemeten gevallen op 2026-08-16:

    1. `GWS_IMPERSONATE_EMAIL` gevuld — en op een werkstation dat het portaal lokaal draait
       staat hij dat — gaf 9 failures in `test_auth.py`; groen zonder.
    2. `test_bron_config.py` post `JIRA_PROJECTS: "ISO"` naar de config-API, waarna
       `naar_omgeving()` dat in `os.environ` zet. Dat lekte naar
       `test_pipeline_ingest.py::test_jira_zonder_scope_stuurt_geen_lege_query`, die het
       onbegrensd-vangnet (`updated >= -365d`) verwacht en `project in ("ISO")` kreeg. Rood
       in CI, groen op een werkstation met een `.env` — het vervelendste soort verschil,
       want de suite die je zelf draait zegt dan dat er niets aan de hand is.

    Autouse en repo-breed, niet per testfile: dit raakt elke test die credentials bouwt of
    een JQL asserteert, en een test die eraan moet dénken zichzelf te isoleren vergeet het
    uiteindelijk. Zie de testisolatie-regel in `~/.claude/CLAUDE.md`.

    De bescherming zit in het opschonen vóór élke test, niet in de teardown: `delenv` met
    `raising=False` legt niets vast als de variabele afwezig was, en zet dan achteraf ook
    niets terug. Een test die zélf in `os.environ` schrijft lekt dus nog steeds — alleen
    bereikt die lek geen enkele volgende test meer.
    """
    for var in _OMGEVING_DIE_TESTS_BEINVLOEDT:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def _eigen_audit_db(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wijs `AUDIT_DB_PATH` naar een wegwerpmap, voor élke test.

    Zonder dit valt `store.db_pad()` terug op `output/audit.db` **binnen de repo** — de
    echte audit-DB van deze werkplek. Gemeten op 2026-08-20: drie tests van
    `test_assistent_route.py` schreven zo drie rijen in de echte `assistent_vragen`-tabel.
    Groene suite, vervuilde audit-trail, en in een append-only tabel valt dat niet netjes
    terug te draaien.

    Autouse en repo-breed, om dezelfde reden als `_schone_omgeving`: een test die eraan moet
    dénken zichzelf te isoleren, vergeet het uiteindelijk. Een test die een eigen pad wil,
    zet `AUDIT_DB_PATH` gewoon zelf — dat overschrijft dit.

    Zie de testisolatie-regel in `~/.claude/CLAUDE.md`.
    """
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path_factory.mktemp("audit-db") / "audit.db"))


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
