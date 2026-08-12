"""Gedeelde route-afhankelijkheden: een audit openen en activiteit vastleggen.

Eén plek waar een audit-id in een `AuditSession` verandert, zodat de drie
route-modules (`routes_audit`, `routes_triage`, `routes_memo`) niet elk hun eigen
variant krijgen. Een tweede opener zou onvermijdelijk net iets anders met een
onbekend id omgaan, en "onbekende audit" is precies het geval waarin je geen
creativiteit wil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException
from starlette.requests import Request

from iso_audit.api.auth_gate import identiteit_van
from iso_audit.api.registry import AuditRegistry, RegistryError
from iso_audit.api.session import AuditSession


@dataclass(slots=True)
class Audits:
    """Opent audits als sessie en registreert wie er muteert.

    **Sessies worden gecachet per audit-id**, en dat is geen optimalisatie. De
    voortgang van een lopende run leeft in het `AuditSession`-object (`_run`); een
    verse sessie per request zou `GET /run/progress` altijd `idle` laten zeggen
    terwijl de run draait. Findings en trail worden nog steeds bij elke aanroep van
    schijf gelezen, dus de cache introduceert geen verouderde data — alleen de
    in-memory run-status blijft bestaan.

    Dat werkt omdat het portaal bewust één replica heeft (ReadWriteOnce-PVC, één
    schrijver per audit). Bij opschalen naar meerdere replicas moet run-status naar
    schijf; dat staat als aandachtspunt in de change.
    """

    registry: AuditRegistry
    profile: str
    norms_dir: str | Path
    _sessies: dict[str, AuditSession] = field(default_factory=dict)

    def dir(self, audit_id: str) -> Path:
        """Directory van een bestaande audit, of 404 — nooit stil aanmaken.

        Een verzoek met een onbekend id is een fout van de client, niet een
        uitnodiging om een audit te verzinnen: in een append-only trail is een
        beslissing in de verkeerde audit niet terug te draaien.
        """
        try:
            return self.registry.eis(audit_id)
        except RegistryError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    def sessie(self, audit_id: str) -> AuditSession:
        """Geef de `AuditSession` van deze audit, uit de cache of nieuw geopend.

        De klasse zelf is ongewijzigd — alleen de manier waarop hij wordt aangewezen
        verandert: niet één keer bij app-start, maar per audit op het moment dat er
        naar gevraagd wordt.
        """
        bestaand = self._sessies.get(audit_id)
        if bestaand is not None:
            return bestaand
        d = self.dir(audit_id)
        sessie = AuditSession(
            d,
            profile=self.profile,
            norms_dir=self.norms_dir,
            memo_input_path=d / "memo-input.yaml",
        )
        self._sessies[audit_id] = sessie
        return sessie

    def muteert(self, audit_id: str, request: Request) -> str:
        """Leg vast dat hier iemand muteert en geef diens identiteit terug.

        Dit is de bron voor de gelijktijdigheids-waarschuwing. Bewust geen slot: zie
        `AuditRegistry.andere_actief`.
        """
        wie = identiteit_van(request)
        self.registry.markeer_actief(audit_id, wie)
        return wie
