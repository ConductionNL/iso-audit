"""Anthropic-auth via het CLI-profiel, zodat een abonnement bruikbaar is.

## Waarom dit geen tweede aanroeppad is

De SDK lost credentials zelf op in de volgorde API-key → auth-token → CLI-profiel →
workload identity → default-profiel. Een kale `anthropic.Anthropic()` — precies wat
`classification/findings.py`, `llm.py` en `thema.py` al gebruiken — pikt een CLI-profiel
automatisch op. Deze module hoeft dus alleen het profiel te *maken*; er verandert niets
aan hoe de classifier de API aanroept.

## De browserstap

`ant auth login --no-browser` print een authorize-URL en wacht daarna op de code. Dat is
één proces dat twee HTTP-requests overspant: het portaal start het, geeft de URL aan de
auditor, en levert later de code aan. Lopende logins staan daarom in het geheugen met een
harde vervaltijd — een pod-restart verliest ze, en dat is prima: opnieuw beginnen kost
één klik.

## Wat hier nooit gebeurt

De code die de auditor plakt en de inhoud van het profiel worden niet gelogd en niet
teruggegeven. Foutmeldingen zijn genormaliseerd: de ruwe CLI-output kan een URL met
credential bevatten.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

_log = logging.getLogger("iso_audit.audit")

ANT_BIN_ENV = "ISO_AUDIT_ANT_BIN"
"""Pad naar de Anthropic-CLI. Alleen gezet in tests, die een stub gebruiken in plaats
van een echte OAuth-flow tegen iemands account."""

CONFIG_DIR_ENV = "ANTHROPIC_CONFIG_DIR"
"""Waar de CLI het profiel bewaart. In de pod een map op de PVC, zodat een login een
herstart overleeft."""

LOGIN_TIMEOUT = timedelta(minutes=10)
"""Hoe lang een halve login blijft staan. Ruim genoeg voor een browserstap, kort genoeg
om geen wachtende processen te laten hangen."""

_URL = re.compile(r"https://\S+")
_PROCES_TIMEOUT_S = 20.0


class AuthError(RuntimeError):
    """Genormaliseerde fout. Bevat nooit ruwe CLI-output."""


@dataclass(slots=True)
class _Login:
    proces: subprocess.Popen[str]
    url: str
    gestart: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def verlopen(self) -> bool:
        return datetime.now(UTC) - self.gestart > LOGIN_TIMEOUT


_lopend: dict[str, _Login] = {}


def _bin() -> str:
    pad = os.environ.get(ANT_BIN_ENV) or "ant"
    gevonden = shutil.which(pad) or (pad if os.path.isfile(pad) else None)
    if not gevonden:
        raise AuthError(
            "De Anthropic-CLI is niet beschikbaar in deze omgeving. "
            "Gebruik de API-key-modus, of laat een beheerder de CLI toevoegen."
        )
    return gevonden


def _omgeving() -> dict[str, str]:
    """Omgeving voor de CLI, met de API-key eruit.

    Een gezette API-key laat de CLI en de SDK die key gebruiken in plaats van het
    profiel — ook een lege string. Bij een login-flow is dat altijd verkeerd.
    """
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    return env


def _draai(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_bin(), *args],
        capture_output=True,
        text=True,
        timeout=_PROCES_TIMEOUT_S,
        env=_omgeving(),
        check=False,
    )


def status() -> dict[str, object]:
    """Is er een actieve credential? Genormaliseerd, zonder CLI-output door te geven."""
    try:
        klaar = _draai("auth", "status")
    except AuthError as exc:
        return {"actief": False, "reden": str(exc)}
    except (OSError, subprocess.SubprocessError):
        return {"actief": False, "reden": "De CLI kon niet worden uitgevoerd."}

    if klaar.returncode != 0:
        return {"actief": False, "reden": "Geen actieve Anthropic-sessie."}
    return {"actief": True, "reden": ""}


def start_login() -> tuple[str, str]:
    """Start een login en geef `(sessie_id, authorize_url)`.

    De auditor opent de URL zelf; het portaal heeft geen browser en hoort er ook geen te
    hebben. Daarna komt de code terug via `voltooi_login`.
    """
    _ruim_op()
    try:
        proces = subprocess.Popen(
            [_bin(), "auth", "login", "--no-browser"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=_omgeving(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthError("De login kon niet worden gestart.") from exc

    url = _lees_url(proces)
    sessie = uuid.uuid4().hex
    _lopend[sessie] = _Login(proces=proces, url=url)
    # De sessie-id wel loggen, de URL niet: die hoort bij één login-poging.
    _log.info('{"event": "anthropic_login_gestart", "sessie": "%s"}', sessie)
    return sessie, url


def _lees_url(proces: subprocess.Popen[str]) -> str:
    """Lees regels tot er een URL langskomt. Geen URL = de flow werkt niet."""
    assert proces.stdout is not None
    for _ in range(40):
        regel = proces.stdout.readline()
        if not regel:
            break
        gevonden = _URL.search(regel)
        if gevonden:
            return gevonden.group(0)
    proces.kill()
    raise AuthError("De CLI gaf geen authorize-URL terug.")


def voltooi_login(sessie: str, code: str) -> None:
    """Lever de code aan. Slaagt of werpt een genormaliseerde fout."""
    login = _lopend.pop(sessie, None)
    if login is None:
        raise AuthError("Deze login is verlopen of onbekend. Begin opnieuw.")
    if login.verlopen:
        login.proces.kill()
        raise AuthError("Deze login is verlopen. Begin opnieuw.")
    if not code.strip():
        login.proces.kill()
        raise AuthError("Er is geen code ingevuld.")

    try:
        # De code wordt hier aangeleverd en verder nergens bewaard of gelogd.
        login.proces.communicate(input=code.strip() + "\n", timeout=_PROCES_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        login.proces.kill()
        raise AuthError("De login liep vast. Begin opnieuw.") from exc

    if login.proces.returncode != 0:
        raise AuthError("De code is niet geaccepteerd. Controleer hem en probeer opnieuw.")
    _log.info('{"event": "anthropic_login_voltooid", "sessie": "%s"}', sessie)


def uitloggen() -> None:
    """Wis het profiel, zodat een auditor zijn sessie kan beëindigen."""
    try:
        klaar = _draai("auth", "logout")
    except (OSError, subprocess.SubprocessError) as exc:
        raise AuthError("Uitloggen is niet gelukt.") from exc
    if klaar.returncode != 0:
        raise AuthError("Uitloggen is niet gelukt.")
    _log.info('{"event": "anthropic_uitgelogd"}')


def _ruim_op() -> None:
    """Beëindig verlopen halve logins; anders blijven processen hangen."""
    for sessie in [s for s, login in _lopend.items() if login.verlopen]:
        _lopend.pop(sessie).proces.kill()
