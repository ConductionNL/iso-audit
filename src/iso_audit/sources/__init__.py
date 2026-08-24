"""Source-adapters: pluggable bronnen voor de audit-pipeline.

Concrete adapters (Drive, Planning, Jira, MCP, REST, …) leven in submodules
en registreren zichzelf via :func:`register` of de :func:`register` decorator.

Voorbeeld
---------

.. code-block:: python

    from iso_audit.sources import register, Source

    @register
    class DriveSource:
        naam = "drive"
        def list_documents(self, filter=None): ...
        def fetch_content(self, doc): ...
        def list_findings(self, sessie_id): ...
        def healthcheck(self): ...

    # Elders in de pipeline:
    from iso_audit.sources import get, available
    adapter = get("drive")
    print(available())  # ["drive"]
"""

from __future__ import annotations

from iso_audit.sources.base import Document, Finding, Source

__all__ = [
    "Document",
    "Finding",
    "Source",
    "available",
    "get",
    "laad_adapters",
    "register",
]


# Module-level registry. Bewust geen class — een registry is staat van het
# proces, en class-instantie-juggling voegt complexiteit toe zonder waarde.
_REGISTRY: dict[str, type[Source]] = {}

_GEBUNDELD: dict[str, type[Source]] = {}
"""Elke adapter die ooit is geregistreerd, en die lijst wordt nooit geleegd.

`_REGISTRY` is de werkende registry en kan door tests worden leeggemaakt; deze bewaart wat er
in het pakket zit, zodat `laad_adapters()` hem kan herstellen ook als de modules al
geïmporteerd waren."""

_ADAPTERMODULES: tuple[str, ...] = ("drive", "jira", "nextcloud", "planning")
"""Modules die bij `laad_adapters()` geïmporteerd worden zodat hun `@register` draait.

Bewust een expliciete lijst en geen automatische ontdekking: welke adapters een installatie
kent, hoort leesbaar te zijn en niet af te hangen van wat er toevallig in de map staat.
`tests/sources/test_registry_bootstrap.py` vergelijkt de lijst met het pakket, zodat een nieuwe
adapter niet stil buiten de boot valt."""


def laad_adapters() -> None:
    """Importeer de gebundelde adapters zodat ze in de registry staan. Idempotent.

    De `@register`-decorator draait pas bij import. Stond die import nergens, dan bestaat de
    adapter niet voor `get(naam)` — zonder melding bij het opstarten, alleen een `KeyError` op
    het moment dat iemand hem gebruikt. Dat gebeurde op 2026-08-24 twee keer: de preflight
    meldde Jira als niet beschikbaar, en een los proces kreeg "Source-adapter 'nextcloud' niet
    geregistreerd. Beschikbaar: drive". In beide gevallen bestond de adapter gewoon.

    Deze functie hoorde hier en niet in `ingest.beschikbare_bronnen()`: de registry vullen is
    geen bijwerking van het opvragen van een lijst.
    """
    import importlib

    for module in _ADAPTERMODULES:
        importlib.import_module(f"iso_audit.sources.{module}")
    # Een module die al in `sys.modules` staat, draait zijn `@register` niet opnieuw. Zonder
    # deze herstelstap zou `laad_adapters()` na een lege registry níets doen — en dan hangt het
    # gedrag af van de vraag wie er eerder toevallig heeft geïmporteerd. Precies de
    # volgorde-afhankelijkheid die deze functie moest wegnemen.
    for naam, adapter in _GEBUNDELD.items():
        _REGISTRY.setdefault(naam, adapter)


def register(adapter_class: type[Source]) -> type[Source]:
    """Registreer een Source-adapter class.

    Bruikbaar als decorator of als directe call. Het ``naam`` class-attribute van
    de adapter wordt gebruikt als registry-sleutel.

    :raises ValueError: bij dubbele registratie van dezelfde naam.
    :raises AttributeError: als ``adapter_class`` geen ``naam`` attribuut heeft.
    """
    naam = adapter_class.naam
    if not isinstance(naam, str) or not naam:
        msg = (
            f"Source-adapter {adapter_class!r} mist een geldige `naam`-attribute "
            "(class-level, lowercase, niet-leeg)."
        )
        raise AttributeError(msg)
    if naam in _REGISTRY:
        msg = (
            f"Source-adapter met naam {naam!r} is al geregistreerd "
            f"({_REGISTRY[naam]!r}). Een naam mag maar door één adapter worden gebruikt."
        )
        raise ValueError(msg)
    _REGISTRY[naam] = adapter_class
    # Bewust overschrijven en niet `setdefault`: herlaadt een test de module, dan is er een
    # nieuw class-object en moet dát het bewaarde zijn. Anders herstelt `laad_adapters()` de
    # oude class en is `get("planning") is planning.PlanningSource` opeens onwaar.
    _GEBUNDELD[naam] = adapter_class
    return adapter_class


def available() -> list[str]:
    """Retourneer alle geregistreerde adapter-namen, gesorteerd."""
    return sorted(_REGISTRY)


def get(naam: str) -> type[Source]:
    """Geef de adapter-class terug die op ``naam`` is geregistreerd.

    :raises KeyError: met een leesbare lijst van beschikbare adapters wanneer
        ``naam`` niet bekend is.
    """
    try:
        return _REGISTRY[naam]
    except KeyError as exc:
        beschikbaar = ", ".join(available()) or "(geen)"
        msg = f"Source-adapter {naam!r} niet geregistreerd. Beschikbaar: {beschikbaar}"
        raise KeyError(msg) from exc


def _reset_for_tests() -> None:
    """Helper voor tests die met de registry willen rommelen.

    Niet onderdeel van de publieke API; tests importeren expliciet via dit
    underscore-prefix-mechanisme. Wordt nooit gebruikt door productie-code.
    """
    _REGISTRY.clear()
