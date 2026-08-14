"""Waarden van bron-configuratie: opslaan, in de omgeving zetten, en vastleggen.

De catalogus (`bron_catalogus.py`) zegt wát een bron nodig heeft; deze module bewaart
de ingevulde waarden zodat een auditor een bron in de UI kan koppelen.

## Waarom via de omgeving

De Source-adapters lezen hun configuratie uit env-vars bij `__init__`. Deze module zet
de opgeslagen waarden in `os.environ` — dan werken alle adapters ongewijzigd en blijft
de Source-architectuur intact. Geen adapter hoeft te weten dat er een portaal bestaat.

## Waar de waarden staan

Twee backends achter dezelfde interface:

1. **Kubernetes-Secret** wanneer `ISO_AUDIT_CONFIG_SECRET` gezet is en er een
   serviceaccount-token in de pod ligt. Dat is de plek waar een beheerder credentials
   verwacht, met RBAC en kube-API-auditlogging eromheen.
2. **JSON op de PVC** (mode 0600) als terugval — lokaal draaien, of levering aan een partij
   zonder Kubernetes. Zonder die terugval is het tool niet meer buiten dit cluster te
   draaien, en dat was juist de reden om configuratie uit het cluster te halen.

Dit is in beide gevallen géén secret-manager met eigen sleutelbeheer.

Wat er tegenover staat: geheime velden worden nooit teruggegeven via de API, en elke
wijziging staat append-only met identiteit en tijdstip in `bron_config_log.jsonl`. Dat
registreren is de controle, niet het moeilijk maken van configureren.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from iso_audit.api import bron_catalogus as cat
from iso_audit.config import secret_store

_log = logging.getLogger("iso_audit.audit")

WAARDEN = "bron_config.json"
LOG = "bron_config_log.jsonl"


class ConfigError(ValueError):
    """Ongeldige configuratie-invoer."""


def _nu() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class BronConfig:
    """Bron-configuratie onder één root-directory (de PVC)."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.pad = self.root / WAARDEN
        self.log_pad = self.root / LOG

    # --- lezen ---------------------------------------------------------------

    def _laad(self) -> dict[str, dict[str, str]]:
        if secret_store.beschikbaar():
            try:
                return secret_store.lees()
            except secret_store.SecretStoreError as exc:
                # Terugvallen in plaats van breken: een auditor die zijn configuratie niet
                # kan zien, kan hem ook niet repareren.
                _log.warning('{"event": "secret_store_terugval", "reden": %r}', str(exc))
        return self._laad_pvc()

    def _laad_pvc(self) -> dict[str, dict[str, str]]:
        if not self.pad.is_file():
            return {}
        try:
            data = json.loads(self.pad.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return {str(k): {str(vk): str(vv) for vk, vv in v.items()} for k, v in data.items()}

    def ui_waarden(self) -> dict[str, str]:
        """Alle via de UI ingevulde waarden, gesleuteld op env-naam.

        Dit is wat deze store bijdraagt aan de precedence-keten in
        `config.settings.load_config` — de laagste van de drie bronnen. De store hoeft
        daardoor niets te weten van puntpaden of van de andere bronnen.
        """
        plat: dict[str, str] = {}
        for velden in self._laad().values():
            for naam, waarde in velden.items():
                if waarde:
                    plat[naam] = waarde
        return plat

    def naar_omgeving(self) -> None:
        """Zet alle opgeslagen waarden in ``os.environ``.

        Bij het starten aangeroepen, en na elke wijziging. Waarden die al in de omgeving
        staan (uit het deployment-manifest of een Secret) worden **niet** overschreven:
        wat een beheerder expliciet heeft gezet, weegt zwaarder dan wat er ooit via de UI
        is ingevuld.
        """
        for velden in self._laad().values():
            for naam, waarde in velden.items():
                if waarde and not os.environ.get(naam):
                    os.environ[naam] = waarde

    def status(self, bron: str) -> dict[str, Any]:
        """Per veld: is het ingesteld, en zo ja met welke waarde (geheim → nooit).

        Geheime velden geven alleen ``ingesteld: true``. Invoeren moet kunnen, teruglezen
        hoeft nooit — en een waarde die niet uit te lezen is, kan ook niet lekken.
        """
        d = cat.definitie(bron)
        if d is None:
            raise ConfigError(f"Onbekende bron: {bron!r}")
        opgeslagen = self._laad().get(bron, {})
        velden: list[dict[str, Any]] = []
        for v in d.velden:
            uit_omgeving = os.environ.get(v.naam) or ""
            waarde = opgeslagen.get(v.naam) or uit_omgeving
            velden.append(
                {
                    "naam": v.naam,
                    "label": v.label,
                    "geheim": v.geheim,
                    "verplicht": v.verplicht,
                    "hint": v.hint,
                    "ingesteld": bool(waarde),
                    "waarde": "" if v.geheim else waarde,
                }
            )
        return {
            "naam": d.naam,
            "label": d.label,
            "uitleg": d.uitleg,
            "eigen_kaart": d.eigen_kaart,
            "velden": velden,
        }

    def alles(self) -> list[dict[str, Any]]:
        return [self.status(b.naam) for b in cat.catalogus()]

    # --- schrijven -----------------------------------------------------------

    def zet(self, bron: str, velden: dict[str, str], *, door: str) -> None:
        """Sla waarden op, zet ze in de omgeving en leg de wijziging vast.

        Een leeg meegegeven veld wist de waarde — anders kun je een verkeerd ingevulde
        bron niet meer loskoppelen. Onbekende veldnamen worden geweigerd in plaats van
        stil bewaard.
        """
        d = cat.definitie(bron)
        if d is None:
            raise ConfigError(f"Onbekende bron: {bron!r}")
        toegestaan = {v.naam: v for v in d.velden}
        onbekend = sorted(set(velden) - set(toegestaan))
        if onbekend:
            raise ConfigError(f"Onbekende velden voor {bron!r}: {', '.join(onbekend)}")

        alle = self._laad()
        huidig = alle.setdefault(bron, {})
        gewijzigd: list[str] = []
        for naam, waarde in velden.items():
            nieuw = waarde.strip()
            if nieuw == huidig.get(naam, ""):
                continue
            if nieuw:
                huidig[naam] = nieuw
            else:
                huidig.pop(naam, None)
                os.environ.pop(naam, None)
            gewijzigd.append(naam)
            if nieuw:
                os.environ[naam] = nieuw

        if not gewijzigd:
            return

        self._bewaar(alle)
        self._log(bron, gewijzigd, toegestaan, door)

    def _bewaar(self, alle: dict[str, dict[str, str]]) -> None:
        """Schrijf naar het Secret als dat kan, anders naar de PVC."""
        if secret_store.beschikbaar():
            try:
                secret_store.schrijf(alle)
                return
            except secret_store.SecretStoreError as exc:
                _log.warning('{"event": "secret_store_terugval_schrijven", "reden": %r}', str(exc))

        self.root.mkdir(parents=True, exist_ok=True)
        self.pad.write_text(json.dumps(alle, ensure_ascii=False, indent=1), encoding="utf-8")
        # Alleen de eigenaar mag dit bestand lezen: er kunnen tokens in staan.
        self.pad.chmod(0o600)

    def _log(
        self, bron: str, gewijzigd: list[str], toegestaan: dict[str, cat.Veld], door: str
    ) -> None:
        """Append-only spoor. Alleen veldnamen, nooit waarden."""
        regel = {
            "ts": _nu(),
            "door": door,
            "bron": bron,
            "velden": sorted(gewijzigd),
            "geheim": sorted(n for n in gewijzigd if toegestaan[n].geheim),
        }
        with self.log_pad.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(regel, ensure_ascii=False) + "\n")

    def wijzigingen(self) -> list[dict[str, Any]]:
        if not self.log_pad.is_file():
            return []
        regels: list[dict[str, Any]] = []
        for r in self.log_pad.read_text(encoding="utf-8").splitlines():
            if r.strip():
                try:
                    regels.append(json.loads(r))
                except json.JSONDecodeError:
                    continue
        return regels
