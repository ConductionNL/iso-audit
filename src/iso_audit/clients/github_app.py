"""GitHub App als bron-credential, zodat de koppeling niet aan één persoon hangt.

Een fijnmazig PAT is altijd van een persoon. Vertrekt die persoon, dan valt de bron stil en staat
er in de volgende audit "bron niet beschikbaar" waar bewijs had moeten staan. Een App is
eigendom van de organisatie en overleeft dat.

Wat per persoon blijft: het **aanmaken**. GitHub heeft dat bewust niet in de API — de
Authorizations API is in 2020 verwijderd, en een App aanmaken gaat via de browser. Wat hier
staat, is het stuk dat automatiseerbaar is: uit App-id, installatie-id en private key een
installatietoken minten.

Twee eigenschappen van GitHub die het gedrag hier bepalen:

1. **De JWT moet RS256 zijn en mag hoogstens tien minuten geldig zijn.** Langer wordt geweigerd.
   `iat` staat bewust een minuut in het verleden: een paar seconden klokverschil tussen pod en
   GitHub is genoeg om een JWT met `iat` in de toekomst te laten afketsen.
2. **Een installatietoken leeft een uur.** Daarom wordt het gecached tot vijf minuten voor het
   verval — elke aanroep opnieuw minten is een extra ronde per repository, en een token dat
   midden in een run verloopt laat een halve audit mislukken.

Ondertekend met `cryptography` en niet met PyJWT: die zat er al (via `google-auth`) en is nu
expliciet gedeclareerd. Twintig regels eigen code tegenover een extra afhankelijkheid in een
project dat onder 27001-scope valt.

**De private key komt hier nergens uit.** Niet in een log, niet in een foutmelding, niet in een
healthcheck. `tests/clients/test_github_app.py` faalt zodra dat verandert.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Protocol

import requests
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

logger = logging.getLogger(__name__)

APP_ID_ENV = "REPO_GITHUB_APP_ID"
INSTALLATIE_ENV = "REPO_GITHUB_APP_INSTALLATION_ID"
PRIVATE_KEY_ENV = "REPO_GITHUB_APP_PRIVATE_KEY"

JWT_GELDIGHEID = 540
"""Negen minuten. GitHub weigert meer dan tien; negen laat ruimte voor klokverschil."""

KLOK_MARGE = 60
"""Hoeveel `iat` in het verleden staat, tegen klokverschil tussen pod en GitHub."""

VERNIEUW_MARGE = 300
"""Hoeveel eerder dan het verval een installatietoken wordt vernieuwd."""

TIMEOUT = 20


class AppAuthError(Exception):
    """De App-gegevens zijn niet te gebruiken."""


class _Poster(Protocol):
    """Wat hier van een HTTP-sessie nodig is.

    Losser getypeerd dan de aanroep, want `requests.Session.post` neemt `headers` en `timeout`
    via `**kwargs`. Een strakker protocol zou `Session` uitsluiten en dan zou de echte code niet
    door de type-check komen — precies verkeerd om.
    """

    def post(self, url: str, **kwargs: Any) -> Any: ...


def _b64(ruw: bytes) -> str:
    return base64.urlsafe_b64encode(ruw).rstrip(b"=").decode("ascii")


def bouw_jwt(app_id: str, private_key: str, *, nu: int | None = None) -> str:
    """Bouw de RS256-JWT waarmee de App zich bij GitHub meldt.

    `nu` is injecteerbaar zodat een test niet van de klok afhangt.

    De foutmelding noemt de sleutel nooit — een melding met een private key erin is een
    incident en geen melding.
    """
    moment = int(time.time()) if nu is None else nu
    try:
        geladen = serialization.load_pem_private_key(private_key.encode("utf-8"), password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm) as fout:
        raise AppAuthError(
            f"de GitHub-App private key is niet te lezen ({type(fout).__name__}); "
            "verwacht een PEM-blok zoals GitHub het levert"
        ) from None
    if not isinstance(geladen, rsa.RSAPrivateKey):
        raise AppAuthError("de GitHub-App private key moet een RSA-sleutel zijn")

    kop = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    lijf = _b64(
        json.dumps(
            {"iat": moment - KLOK_MARGE, "exp": moment + JWT_GELDIGHEID, "iss": app_id},
            separators=(",", ":"),
        ).encode()
    )
    ondertekend = geladen.sign(f"{kop}.{lijf}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{kop}.{lijf}.{_b64(ondertekend)}"


class AppCredential:
    """Levert een installatietoken, en vernieuwt het voordat het verloopt."""

    def __init__(
        self,
        app_id: str,
        installatie_id: str,
        private_key: str,
        *,
        sessie: _Poster | None = None,
        basis: str = "https://api.github.com",
    ) -> None:
        self._app_id = app_id
        self._installatie = installatie_id
        self._key = private_key
        self._sessie: _Poster | requests.Session = (
            sessie if sessie is not None else requests.Session()
        )
        self._basis = basis
        self._token = ""
        self._geldig_tot = 0.0

    def token(self) -> str:
        if self._token and time.time() < self._geldig_tot - VERNIEUW_MARGE:
            return self._token
        self._vernieuw()
        return self._token

    def _vernieuw(self) -> None:
        jwt = bouw_jwt(self._app_id, self._key)
        antwoord = self._sessie.post(
            f"{self._basis}/app/installations/{self._installatie}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt}",
                "Accept": "application/vnd.github+json",
            },
            timeout=TIMEOUT,
        )
        if antwoord.status_code != 201:
            raise AppAuthError(
                f"GitHub gaf {antwoord.status_code} op het installatietoken; "
                "controleer App-id, installatie-id en of de App op de organisatie staat"
            )
        gegevens = antwoord.json()
        self._token = str(gegevens.get("token") or "")
        if not self._token:
            raise AppAuthError("GitHub gaf een leeg installatietoken terug")
        self._geldig_tot = _naar_tijdstip(str(gegevens.get("expires_at") or ""))
        logger.info(
            "GitHub-App-token vernieuwd voor installatie %s, geldig tot %s",
            self._installatie,
            gegevens.get("expires_at"),
        )


def _naar_tijdstip(iso: str) -> float:
    """`2026-08-26T13:00:00Z` → epoch. Onleesbaar? Dan een uur, het GitHub-standaardverval.

    Expliciet UTC, want `strptime` levert een naïeve datetime en `.timestamp()` leest die dan als
    **lokale** tijd. In CEST maakt dat het token twee uur te oud — dan werkt de cache nooit en
    mint elke aanroep opnieuw. In een negatieve tijdzone is het erger: dan wordt een verlopen
    token voor geldig gehouden.
    """
    try:
        return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return time.time() + 3600
