"""Waarden van bron-configuratie: opslaan, in de omgeving zetten, en vastleggen.

De catalogus (`bron_catalogus.py`) zegt wát een bron nodig heeft; deze module bewaart
de ingevulde waarden zodat een auditor een bron in de UI kan koppelen.

## Waarom via de omgeving

De Source-adapters lezen hun configuratie uit env-vars bij `__init__`. Deze module zet
de opgeslagen waarden in `os.environ` — dan werken alle adapters ongewijzigd en blijft
de Source-architectuur intact. Geen adapter hoeft te weten dat er een portaal bestaat.

## Wat dit wel en niet is

Dit is géén secret-manager. De waarden staan als JSON op de PVC, mode 0600, in dezelfde
volume als de audit-trail. Zwakker dan een cluster-Secret, en dat is een bewuste ruil:
configuratie die alleen via Secrets kan, maakt het tool onleverbaar aan derden — dan
heeft elke partij een Kubernetes-beheerder nodig om te beginnen.

Wat er tegenover staat: geheime velden worden nooit teruggegeven via de API, en elke
wijziging staat append-only met identiteit en tijdstip in `bron_config_log.jsonl`. Dat
registreren is de controle, niet het moeilijk maken van configureren.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from iso_audit.api import bron_catalogus as cat

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
        if not self.pad.is_file():
            return {}
        try:
            data = json.loads(self.pad.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return {str(k): {str(vk): str(vv) for vk, vv in v.items()} for k, v in data.items()}

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
        return {"naam": d.naam, "label": d.label, "uitleg": d.uitleg, "velden": velden}

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

        self.root.mkdir(parents=True, exist_ok=True)
        self.pad.write_text(json.dumps(alle, ensure_ascii=False, indent=1), encoding="utf-8")
        # Alleen de eigenaar mag dit bestand lezen: er kunnen tokens in staan.
        self.pad.chmod(0o600)
        self._log(bron, gewijzigd, toegestaan, door)

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
