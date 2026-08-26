"""Interface-definities voor de auditmemo-pijplijn.

Vijf protocollen zodat implementaties (norm-lookup, classifier, renderer, ...)
los uitwisselbaar zijn en de afhankelijkheden expliciet blijven — boring &
auditable. Concrete implementaties leven in de zustermodules.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from iso_audit.memo.models import (
    AuditMemo,
    ClauseCitation,
    Finding,
)

if TYPE_CHECKING:
    from iso_audit.memo.theme.profile import Profile


@runtime_checkable
class NormLookup(Protocol):
    """Levert genormeerde clausule-citaten uit de norm-database."""

    def citation(self, standard: str, clause: str, language: str) -> ClauseCitation:
        """Geef het citaat voor (standard, clause) in ``language``.

        MUST een harde fout gooien als de clausule niet bestaat — nooit een
        verzonnen of leeg citaat teruggeven.
        """
        ...


@runtime_checkable
class FindingsClassifier(Protocol):
    """Scheidt NC's en (gepromote) verbeterpunten uit de findings-dataset."""

    def ncs(self, findings: list[Finding]) -> list[Finding]: ...


@runtime_checkable
class PatternDetector(Protocol):
    """Detecteert cross-clause patronen (positief vs OFI op dezelfde clausule)."""

    def pattern_note(self, clause: str, findings: list[Finding]) -> str | None: ...


@runtime_checkable
class ProfileLoader(Protocol):
    """Laadt en valideert een profiel uit slug (XDG) of absoluut pad."""

    def load(self, slug_or_path: str) -> Profile: ...


@runtime_checkable
class MemoRenderer(Protocol):
    """Rendert de samengestelde memo naar HTML en PDF."""

    def render_html(self, memo: AuditMemo, profile: Profile) -> str: ...

    def render_pdf(self, html: str, output: Path) -> None: ...
