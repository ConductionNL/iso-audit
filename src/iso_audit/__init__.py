"""iso-audit — pluggable ISO 9001 + 27001 audit pipeline.

Drie protocol-lagen vormen de uitbreidbaarheid:

- ``iso_audit.sources``: pluggable bron-adapters (Drive, Planning, Jira, MCP, REST)
- ``iso_audit.sinks``: pluggable schrijf-adapters (rapport-publicatie, externe meldingen)
- ``iso_audit.notifiers``: pluggable handoff-kanalen voor integer-modus (Slack, Email)

Twee runmodes zijn ingebakken (``iso_audit.modes``): ``autonoom`` voor cron-/CI-runs,
``integer`` voor mens-in-de-lus op kritieke beslismomenten.

Zie ``ARCHITECTURE.md`` voor het volledige plaatje en ``docs/missie.md`` voor
de positionering van het tool ten opzichte van de auditor-rol.
"""


def _versie() -> str:
    """De versie uit de pakket-metadata, dus uit `pyproject.toml`.

    Hier stond een losse string. Die liep uit de pas: `pyproject.toml` zei `0.2.0a8`
    terwijl dit `0.1.0a0` meldde. Bij een uitrol is dat geen cosmetiek — het is de string
    waaraan je ziet wélke build draait, en juist daar is een tweede waarheid duur. Eén
    bron, geen synchronisatie.

    De terugval is er voor een omgeving waar het pakket niet geïnstalleerd is (los
    uitgepakte broncode); dan is er geen metadata om te lezen.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("iso-audit")
    except PackageNotFoundError:  # pragma: no cover — alleen zonder installatie
        return "0.0.0+onbekend"


__version__ = _versie()

__all__ = ["__version__"]
