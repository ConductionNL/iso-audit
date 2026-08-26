"""Een GitHub App als bron-credential, zodat de koppeling niet aan één persoon hangt.

Een fijnmazig PAT is altijd van een persoon: vertrekt die persoon, dan valt de bron stil en staat
er in de volgende audit "bron niet beschikbaar" waar bewijs had moeten staan. Een App is
eigendom van de organisatie.

Wat wél per persoon blijft: het **aanmaken**. GitHub heeft dat bewust niet in de API — de
Authorizations API is in 2020 verwijderd, en een App aanmaken gaat via de browser. Wat hier
gebouwd is, is het stuk dat automatiseerbaar is: uit de App-gegevens een installatietoken minten.

Die tokens leven een uur, dus er hoort caching bij. En het belangrijkste: de private key mag
nergens uitkomen — niet in een log, niet in een healthcheck, niet in een foutmelding.
"""

from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from iso_audit.clients import github_app


@pytest.fixture(scope="module")
def sleutel() -> str:
    """Een echte RSA-sleutel; een neppe zou het ondertekenen niet toetsen."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def _deel(jwt: str, index: int) -> dict[str, object]:
    ruw = jwt.split(".")[index]
    ruw += "=" * (-len(ruw) % 4)
    geparsed: dict[str, object] = json.loads(base64.urlsafe_b64decode(ruw))
    return geparsed


def test_de_jwt_is_ondertekend_met_rs256(sleutel: str) -> None:
    """GitHub accepteert alleen RS256 voor App-authenticatie."""
    jwt = github_app.bouw_jwt("12345", sleutel, nu=1_700_000_000)
    assert _deel(jwt, 0) == {"alg": "RS256", "typ": "JWT"}


def test_de_jwt_noemt_de_app_als_uitgever(sleutel: str) -> None:
    payload = _deel(github_app.bouw_jwt("12345", sleutel, nu=1_700_000_000), 1)
    assert payload["iss"] == "12345"


def test_de_jwt_ligt_iets_in_het_verleden(sleutel: str) -> None:
    """GitHub weigert een JWT waarvan `iat` in de toekomst ligt; klokverschil van een paar
    seconden tussen pod en GitHub is genoeg om dat te veroorzaken."""
    nu = 1_700_000_000
    payload = _deel(github_app.bouw_jwt("1", sleutel, nu=nu), 1)
    assert isinstance(payload["iat"], int)
    assert payload["iat"] < nu
    assert nu < int(str(payload["exp"])) <= nu + 600


def test_de_jwt_verloopt_binnen_tien_minuten(sleutel: str) -> None:
    """GitHub weigert een langere geldigheid."""
    nu = 1_700_000_000
    payload = _deel(github_app.bouw_jwt("1", sleutel, nu=nu), 1)
    assert int(str(payload["exp"])) - int(str(payload["iat"])) <= 600


def test_de_signature_is_geen_lege_string(sleutel: str) -> None:
    assert len(github_app.bouw_jwt("1", sleutel, nu=1).split(".")[2]) > 40


def test_een_kapotte_sleutel_geeft_een_nette_fout() -> None:
    with pytest.raises(github_app.AppAuthError, match="private key"):
        github_app.bouw_jwt("1", "dit is geen sleutel", nu=1)


def test_de_fout_bevat_de_sleutel_niet() -> None:
    """Een foutmelding met een private key erin is een incident, geen melding."""
    geheim = "-----BEGIN PRIVATE KEY-----\nGEHEIMEBYTES\n-----END PRIVATE KEY-----"
    with pytest.raises(github_app.AppAuthError) as fout:
        github_app.bouw_jwt("1", geheim, nu=1)
    assert "GEHEIMEBYTES" not in str(fout.value)


# --- installatietoken -------------------------------------------------------


class _NepSessie:
    """Antwoordt als GitHub, en houdt bij hoe vaak er gevraagd is."""

    def __init__(self, verloopt_over: int = 3600) -> None:
        self.aanroepen = 0
        self._verloopt = verloopt_over

    def post(self, url: str, **kwargs: object) -> object:
        self.aanroepen += 1
        verval = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + self._verloopt))
        return type(
            "Antwoord",
            (),
            {
                "status_code": 201,
                "json": lambda self: {"token": "ghs_installatie", "expires_at": verval},
                "text": "",
            },
        )()


def test_het_installatietoken_wordt_opgehaald(sleutel: str) -> None:
    sessie = _NepSessie()
    bron = github_app.AppCredential("1", "42", sleutel, sessie=sessie)
    assert bron.token() == "ghs_installatie"
    assert sessie.aanroepen == 1


def test_het_token_wordt_hergebruikt_binnen_zijn_geldigheid(sleutel: str) -> None:
    """Elke aanroep opnieuw minten is een extra ronde per repository."""
    sessie = _NepSessie()
    bron = github_app.AppCredential("1", "42", sleutel, sessie=sessie)
    bron.token()
    bron.token()
    bron.token()
    assert sessie.aanroepen == 1


def test_een_bijna_verlopen_token_wordt_vernieuwd(sleutel: str) -> None:
    """Een token dat tijdens de run verloopt, laat een halve audit mislukken."""
    sessie = _NepSessie(verloopt_over=60)
    bron = github_app.AppCredential("1", "42", sleutel, sessie=sessie)
    bron.token()
    bron.token()
    assert sessie.aanroepen == 2


# --- aangesloten op de forge-client -----------------------------------------


def test_de_app_heeft_voorrang_op_een_persoonlijk_token(sleutel: str) -> None:
    """Een PAT hangt aan één persoon; is er een App, dan is die de bron van waarheid."""
    from iso_audit.clients.forge import GitHubClient

    client = GitHubClient(
        token="pat_van_iemand",
        credential=github_app.AppCredential("1", "42", sleutel, sessie=_NepSessie()),
    )
    assert client._sessie.headers.get("Authorization") != "Bearer pat_van_iemand"


def test_elke_github_aanroep_loopt_langs_een_doorgang() -> None:
    """De Authorization-kop mag niet per methode hoeven te worden onthouden.

    Eerder stond die actie in elke methode los, en `_bescherming` miste hem — functioneel
    gedekt omdat hij alleen via `repository()` bereikbaar is, maar dat leunt op aanroeporde.
    """
    import inspect

    from iso_audit.clients import forge

    bron = inspect.getsource(forge.GitHubClient)
    lichaam = bron.split("def _get(", 1)[1].split("def ", 1)[1]
    assert "_haal(" not in lichaam, "een GitHub-methode omzeilt _get()"
