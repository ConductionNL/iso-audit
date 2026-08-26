"""Selectie van NC's en verbeterpunten uit de findings-dataset.

Deterministisch en boring: geen LLM, geen verborgen heuristiek. NC's zijn de
findings met severity ``NC``. Verbeterpunten zijn expliciet gepromote OFI's,
aangevuld met OFI-clusters die een drempel overschrijden (één representant per
clausule).
"""

from __future__ import annotations

from iso_audit.memo.models import Finding


class DefaultClassifier:
    """Implementeert het ``FindingsClassifier``-protocol."""

    def ncs(self, findings: list[Finding]) -> list[Finding]:
        """Alle non-conformiteiten, in invoervolgorde."""
        return [f for f in findings if f.severity == "NC"]
