"""UI-configuratie in een Kubernetes-Secret, met de PVC-JSON als terugval.

## Waarom een Secret en niet alleen de PVC

De PVC-variant is platte JSON met mode 0600 naast de audit-trail. Dat werkt, maar een
Secret is de plek waar een cluster-beheerder credentials verwacht en waar bestaande
gereedschappen (RBAC, audit-logging van de kube-API, encryptie-at-rest als het cluster dat
aan heeft) al op zitten.

## Waarom de terugval blijft

Zonder terugval is het tool niet meer buiten dit cluster te draaien — en dat was juist de
reden om configuratie uit het cluster te halen. Lokaal draaien, of levering aan een partij
zonder Kubernetes, valt terug op `bron_config.json` met een waarschuwing.

## Rechten

Eén Role met `resourceNames: ["iso-audit-portal-config"]` en verbs `get`/`patch`. Geen
`list` (dat zou alle Secrets in de namespace opsommen), geen andere naam, geen ClusterRole.
Zie `deploy/rbac-config.yaml`.
"""

from __future__ import annotations

import base64
import http.client
import json
import logging
import os
import ssl
from pathlib import Path
from typing import Any

_log = logging.getLogger("iso_audit.audit")

SECRET_NAAM_ENV = "ISO_AUDIT_CONFIG_SECRET"
"""Naam van het Secret. Niet gezet = geen Secret-backend, alleen de PVC."""

_SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")
_TOKEN = _SA_DIR / "token"
_CA = _SA_DIR / "ca.crt"
_NS = _SA_DIR / "namespace"
_SLEUTEL = "bron_config.json"
"""Sleutel binnen het Secret. Eén sleutel met de hele JSON, zodat de vorm gelijk is aan
de PVC-variant en er geen tweede serialisatie bestaat."""

_TIMEOUT_S = 10.0


class SecretStoreError(RuntimeError):
    """De kube-API is niet bruikbaar; de aanroeper valt terug op de PVC."""


def beschikbaar() -> bool:
    """Is er een Secret-backend geconfigureerd én een SA-token aanwezig?"""
    return bool(os.environ.get(SECRET_NAAM_ENV)) and _TOKEN.is_file()


def _api(pad: str, *, methode: str = "GET", body: bytes | None = None) -> dict[str, Any]:
    """Praat met de kube-API over een expliciete HTTPS-verbinding.

    Bewust `HTTPSConnection` en niet `urlopen`: bij `urlopen` bepaalt een string het
    schema, en een string die ooit `file:` of `http:` wordt is een lek dat je niet ziet.
    Een HTTPSConnection kán geen ander schema — dat is structureel, niet een controle die
    iemand kan vergeten.
    """
    if not _TOKEN.is_file():
        raise SecretStoreError("Geen serviceaccount-token in deze omgeving.")
    host = os.environ.get("KUBERNETES_SERVICE_HOST", "kubernetes.default.svc")
    poort = int(os.environ.get("KUBERNETES_SERVICE_PORT", "443"))
    token = _TOKEN.read_text(encoding="utf-8").strip()

    context = ssl.create_default_context(cafile=str(_CA)) if _CA.is_file() else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if body:
        headers["Content-Type"] = "application/merge-patch+json"

    verbinding = http.client.HTTPSConnection(host, poort, timeout=_TIMEOUT_S, context=context)
    try:
        verbinding.request(methode, pad, body=body, headers=headers)
        antwoord = verbinding.getresponse()
        ruw = antwoord.read()
        if antwoord.status == 404:
            return {}
        if antwoord.status >= 400:
            # Geen responsbody doorgeven: die kan het token in een foutmelding echoën.
            raise SecretStoreError(f"kube-API gaf status {antwoord.status}.")
        geladen = json.loads(ruw.decode("utf-8"))
        return geladen if isinstance(geladen, dict) else {}
    except (OSError, http.client.HTTPException, ValueError) as exc:
        raise SecretStoreError("kube-API niet bereikbaar.") from exc
    finally:
        verbinding.close()


def _namespace() -> str:
    if _NS.is_file():
        return _NS.read_text(encoding="utf-8").strip()
    return os.environ.get("POD_NAMESPACE", "iso-platform")


def _pad() -> str:
    naam = os.environ[SECRET_NAAM_ENV]
    return f"/api/v1/namespaces/{_namespace()}/secrets/{naam}"


def lees() -> dict[str, dict[str, str]]:
    """Lees de opgeslagen configuratie uit het Secret. Leeg als hij niet bestaat."""
    data = _api(_pad()).get("data") or {}
    ruw = data.get(_SLEUTEL)
    if not ruw:
        return {}
    try:
        ontcijferd = base64.b64decode(ruw).decode("utf-8")
        geladen = json.loads(ontcijferd)
    except (ValueError, UnicodeDecodeError):
        _log.warning('{"event": "secret_store_onleesbaar"}')
        return {}
    if not isinstance(geladen, dict):
        return {}
    return {str(k): {str(vk): str(vv) for vk, vv in v.items()} for k, v in geladen.items()}


def schrijf(waarden: dict[str, dict[str, str]]) -> None:
    """Vervang de configuratie in het Secret.

    Merge-patch met één sleutel: het Secret kan andere sleutels bevatten die van een
    beheerder zijn, en die blijven staan.
    """
    inhoud = json.dumps(waarden, ensure_ascii=False)
    patch = {"data": {_SLEUTEL: base64.b64encode(inhoud.encode("utf-8")).decode("ascii")}}
    _api(_pad(), methode="PATCH", body=json.dumps(patch).encode("utf-8"))
    _log.info('{"event": "secret_store_geschreven", "bronnen": %d}', len(waarden))
