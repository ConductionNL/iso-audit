"""Profile-model + loader.

Een profiel is een standalone, overdraagbare YAML-bundle (geen externe
pad-refs). Kleurpalet heeft afgeleide defaults zodat een minimaal profiel
volstaat met primary + logo + org-naam. Loader: XDG-slug of absoluut pad,
``safe_load``, schema_version-check, SVG-validatie.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any

import yaml
from pydantic import BaseModel, Field, model_validator

from iso_audit.memo.theme.svg_validator import OnveiligeSvgError, valideer_svg

SCHEMA_VERSION = 1
_DEFAULT_FONT_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
_HEX = r"^#[0-9a-fA-F]{6}$"
HexColor = Annotated[str, Field(pattern=_HEX)]
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class ProfileError(ValueError):
    """Profiel kon niet geladen of gevalideerd worden."""


def _profiles_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "iso-audit" / "profiles"


def _tint(hex_kleur: str, factor: float = 0.06) -> str:
    """Meng ``hex_kleur`` met wit (factor = aandeel kleur) → lichte brand-tint."""
    r, g, b = (int(hex_kleur[i : i + 2], 16) for i in (1, 3, 5))
    mix = tuple(round(c * factor + 255 * (1 - factor)) for c in (r, g, b))
    return "#{:02x}{:02x}{:02x}".format(*mix)


class ColorPalette(BaseModel):
    primary: HexColor
    accent: HexColor | None = None
    muted: HexColor | None = None
    border: HexColor | None = None
    soft_bg: HexColor | None = None

    @model_validator(mode="after")
    def _vul_defaults(self) -> ColorPalette:
        self.accent = self.accent or self.primary
        self.muted = self.muted or "#6a6a6a"
        self.border = self.border or "#e0e4ec"
        self.soft_bg = self.soft_bg or _tint(self.primary)
        return self


class Organization(BaseModel):
    name: str
    legal_form: str | None = None


class Auditor(BaseModel):
    name: str
    role: str


class Brand(BaseModel):
    logo_svg: str
    colors: ColorPalette
    font_stack: str = _DEFAULT_FONT_STACK


class Defaults(BaseModel):
    language: str = "nl"
    include_independence_caveat: bool = False


class ClausuleContext(BaseModel):
    """Wat er over déze organisatie bekend is bij één clausule.

    Na de volledige run van 2026-08-31 wees de auditor twee NC's aan die het niet zijn: A.8.14
    (redundantie) omdat Conduction data bij de bron ophaalt in plaats van zelf te bewaren, en
    A.8.9 (configuratiebeheer) omdat de versies in Git staan. Beide keren ís er een maatregel,
    alleen niet gedocumenteerd of gecentraliseerd — een verbeterkans, geen non-conformiteit.

    Zonder deze context velt het model elke run opnieuw hetzelfde verkeerde oordeel.

    In het profiel en niet in de code, want het is klantspecifiek: een cachende dienstverlener
    heeft een ander antwoord op A.8.14 dan een partij die zelf data bewaart.
    """

    context: str = ""
    """Wat de auditor over deze organisatie weet en het model niet. Gaat mee naar de
    classificatie als toelichting, niet als gewenste uitkomst."""

    hoogste_klasse: str | None = None
    """`OFI` of `POSITIVE`: hoger dan dit mag een bevinding op deze clausule niet uitvallen.

    Alleen verlagen. Ophogen naar NC is een auditoordeel dat een mens hoort te vellen, in de
    triage, met zijn naam eronder — zie `MACHINE_ACTOREN` in `api/session.py`."""

    thema: str = ""
    """Onder welk memo-thema bevindingen op deze clausule vallen. Moet in `THEMA_LIJST` staan.

    A.8.14 en A.8.9 zijn hetzelfde verhaal — de beheersmaatregel bestáát, hij is alleen niet
    vastgelegd — maar de heuristiek zet ze in `Back-up & continuïteit` en `Ontwikkeling &
    wijzigingsbeheer`. Uit elkaar getrokken worden het twee losse opmerkingen; bij elkaar is het
    één verbeteradvies over documenteren, en dat is wat de directie kan oppakken."""

    motivering: str = ""
    """Waarom die grens er is. Verplicht zodra `hoogste_klasse` is gezet: een klasse verlagen
    zonder reden is precies het soort stille uitzondering waar een externe auditor op doorvraagt.
    Het profiel is versiebeheerd, dus deze zin is later na te lezen."""


class Profile(BaseModel):
    schema_version: int
    slug: str
    organization: Organization
    auditor: Auditor
    brand: Brand
    standards: list[str] = Field(default_factory=list)
    defaults: Defaults = Field(default_factory=Defaults)
    clausule_context: dict[str, ClausuleContext] = Field(default_factory=dict)
    """Per clausule-id de organisatiecontext. Leeg in bestaande profielen; die blijven werken."""


TOEGESTANE_GRENZEN = ("OFI", "POSITIVE")
"""Klassen waarnaar een profiel mag verlagen. `NC` staat er bewust niet bij."""


def _valideer_clausule_context(profiel: Profile) -> None:
    """Een grens vraagt een motivering en mag alleen verlagen; een thema moet bestaan."""
    from iso_audit.classification.thema import THEMA_LIJST

    for clausule, regel in profiel.clausule_context.items():
        if regel.thema and regel.thema not in THEMA_LIJST:
            # Vrije tekst zou per profiel een eigen thema opleveren, en dan bundelt de memo niets
            # meer: twee spellingen van hetzelfde thema zijn twee blokken.
            raise ProfileError(
                f"Profiel '{profiel.slug}', clausule {clausule}: onbekend thema "
                f"{regel.thema!r}. Kies er een uit THEMA_LIJST in classification/thema.py."
            )
        if not regel.hoogste_klasse:
            continue
        if regel.hoogste_klasse == "NC":
            raise ProfileError(
                f"Profiel '{profiel.slug}', clausule {clausule}: `hoogste_klasse` verlaagt "
                "alleen. Een bevinding ophogen naar NC is een auditoordeel dat in de triage "
                "hoort, met een mens-account eronder."
            )
        if regel.hoogste_klasse not in TOEGESTANE_GRENZEN:
            raise ProfileError(
                f"Profiel '{profiel.slug}', clausule {clausule}: onbekende `hoogste_klasse` "
                f"{regel.hoogste_klasse!r}; kies uit {', '.join(TOEGESTANE_GRENZEN)}."
            )
        if not regel.motivering.strip():
            raise ProfileError(
                f"Profiel '{profiel.slug}', clausule {clausule}: `hoogste_klasse` vraagt een "
                "motivering. Een klasse verlagen zonder reden is niet te verantwoorden tegenover "
                "een externe auditor."
            )


def _valideer_policy(profiel: Profile) -> None:
    """Policy-gates die als ProfileError moeten propageren (niet via pydantic).

    Bewust buiten de pydantic-validator: een ValueError dáár wordt verpakt in een
    ValidationError en is niet als ProfileError vangbaar.
    """
    _valideer_clausule_context(profiel)
    if profiel.schema_version != SCHEMA_VERSION:
        msg = (
            f"Profiel '{profiel.slug}' heeft schema_version {profiel.schema_version}; "
            f"deze tool ondersteunt alleen versie {SCHEMA_VERSION}. "
            "Migreer het profiel of gebruik een tool-versie die deze versie kent."
        )
        raise ProfileError(msg)
    try:
        valideer_svg(profiel.brand.logo_svg)
    except OnveiligeSvgError as exc:
        raise ProfileError(str(exc)) from exc


def _resolveer_pad(slug_or_path: str) -> Path:
    """Bepaal het YAML-pad uit een slug (XDG) of een expliciet pad."""
    if os.sep in slug_or_path or slug_or_path.startswith("~") or slug_or_path.endswith(".yaml"):
        pad = Path(slug_or_path).expanduser().resolve()
        if not pad.is_file():
            raise ProfileError(f"Profiel-pad bestaat niet: {pad}")
        return pad
    if not _SLUG_RE.match(slug_or_path):
        raise ProfileError(
            f"Ongeldige profiel-slug {slug_or_path!r}: alleen [a-z0-9_-], geen pad-segmenten."
        )
    base = _profiles_dir().resolve()
    pad = (base / f"{slug_or_path}.yaml").resolve()
    if base not in pad.parents:
        raise ProfileError(f"Profiel-slug resolveert buiten {base} — geweigerd.")
    if not pad.is_file():
        raise ProfileError(f"Profiel '{slug_or_path}' niet gevonden in {base}.")
    return pad


def laad_profiel(slug_or_path: str) -> Profile:
    """Laad + valideer een profiel uit XDG-slug of absoluut/relatief pad."""
    pad = _resolveer_pad(slug_or_path)
    data: Any = yaml.safe_load(pad.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProfileError(f"Profiel {pad} bevat geen geldige YAML-mapping.")
    profiel = Profile(**data)
    _valideer_policy(profiel)
    return profiel


def opslaan_profiel(profiel: Profile, *, overschrijf: bool = False) -> Path:
    """Schrijf een profiel naar de XDG-locatie ``<slug>.yaml``."""
    _valideer_policy(profiel)
    base = _profiles_dir()
    base.mkdir(parents=True, exist_ok=True)
    pad = base / f"{profiel.slug}.yaml"
    if pad.exists() and not overschrijf:
        raise ProfileError(f"Profiel {pad} bestaat al; gebruik overschrijf=True.")
    pad.write_text(
        yaml.safe_dump(profiel.model_dump(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return pad
