"""Google Workspace authenticatie via service account.

Scope-strategie (least privilege):
    - `drive.readonly`     — documenten lezen uit Drive
    - `drive.file`         — alleen bestanden schrijven die de app zelf aanmaakt
    - `documents.readonly` — Google Docs lezen
    - `documents`          — Google Docs schrijven
    - `spreadsheets`       — Google Sheets lezen en schrijven
    - `presentations`      — Google Slides aanmaken
    - `gmail.send`         — e-mail versturen
    - `calendar`           — Calendar-uitnodigingen aanmaken

De echte toegangsmuur is het Drive-deelbeleid: deel het service account
UITSLUITEND met de "Interne Audits"-map. Bestanden buiten die map zijn
voor het account simpelweg onzichtbaar.

Gemigreerd uit `Ops_to_Biz/audit/auth.py` per milestone B §2.2.2.
"""

from __future__ import annotations

import os
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Lezen: alleen de Drive-map die expliciet gedeeld is met het service account.
_READ_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents.readonly",
]

# Schrijven: alleen bestanden die de app zelf aanmaakt (drive.file).
_WRITE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/presentations",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

CREDS_ENV_VAR = "GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE"

IMPERSONATE_ENV_VAR = "GWS_IMPERSONATE_EMAIL"
"""Optioneel. Leeg = het service-account leest alleen wat expliciet met hem gedeeld is.

Gevuld = domain-wide delegation: het service-account handelt namens deze gebruiker en ziet
dus alles wat die gebruiker ziet. Dat vraagt een **eenmalige autorisatie door een
Workspace-super-admin** voor de client-ID van het service-account én precies de scopes
hieronder. Is die autorisatie er niet, dan faalt elke call met `unauthorized_client` — de
configuratie ziet dan compleet uit terwijl er niets werkt, en daarom meldt de
verbindingstest dit verschil expliciet.

De ruimere blik is ook een risico: impersonation omzeilt de map-sharing die anders de
scope van de audit begrenst. Laat dit veld leeg tenzij een bron zonder impersonation
onbereikbaar is.
"""


def _get_credentials(scopes: list[str]) -> Any:
    """Laad de service-account-credentials voor de gevraagde scopes.

    Pad van het JSON-keyfile komt uit env-var `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`.
    Staat `GWS_IMPERSONATE_EMAIL` gevuld, dan handelt het service-account namens die
    gebruiker (domain-wide delegation); zie `IMPERSONATE_ENV_VAR`.

    Returntype is `Any` omdat `google.oauth2.service_account` geen
    runtime-stubs heeft die mypy --strict tevreden stellen.
    """
    creds_file = os.environ.get(CREDS_ENV_VAR)
    if not creds_file:
        raise OSError(f"{CREDS_ENV_VAR} niet ingesteld")
    # google-auth ships zonder volledige type-stubs voor service_account;
    # de call is wel runtime-typed, maar mypy --strict ziet hem als untyped.
    creds = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
        creds_file, scopes=scopes
    )

    namens = (os.environ.get(IMPERSONATE_ENV_VAR) or "").strip()
    if namens:
        # with_subject geeft een nieuw credentials-object; het origineel blijft ongemoeid.
        creds = creds.with_subject(namens)
    return creds


def drive_read_service() -> Any:
    """Drive-service met alleen leesrechten."""
    return build("drive", "v3", credentials=_get_credentials(_READ_SCOPES))


def drive_write_service() -> Any:
    """Drive-service voor aanmaken van bestanden (drive.file scope)."""
    return build("drive", "v3", credentials=_get_credentials(_WRITE_SCOPES))


def docs_read_service() -> Any:
    """Google Docs-service met leesrechten."""
    return build("docs", "v1", credentials=_get_credentials(_READ_SCOPES))


def docs_write_service() -> Any:
    """Google Docs-service voor app-eigen documenten."""
    return build("docs", "v1", credentials=_get_credentials(_WRITE_SCOPES))


def sheets_service() -> Any:
    """Google Sheets-service (lezen + schrijven)."""
    return build("sheets", "v4", credentials=_get_credentials(_WRITE_SCOPES))


def slides_service() -> Any:
    """Google Slides-service voor presentatie-aanmaken."""
    return build("slides", "v1", credentials=_get_credentials(_WRITE_SCOPES))


def gmail_service() -> Any:
    """Gmail-service voor `gmail.send`-scope."""
    return build("gmail", "v1", credentials=_get_credentials(_WRITE_SCOPES))


def calendar_service() -> Any:
    """Google Calendar-service voor uitnodigingen."""
    return build("calendar", "v3", credentials=_get_credentials(_WRITE_SCOPES))
