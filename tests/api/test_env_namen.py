"""Env-namen volgen één patroon, en botsen niet met bekende namen van anderen.

Twee dingen waren mis aan de namen van de twee nieuwe bronnen:

1. **`REPO_GITHUB_TOKEN` botst.** Dat is de naam die GitHub Actions zelf in élke workflow zet. Draait
   dit tool ooit in een Action, dan krijgt het het Actions-token in plaats van het geconfigureerde
   token — met andere rechten, en zonder dat iemand het merkt. Een audit die stilletjes met een
   ander credential leest dan geconfigureerd, is niet te verantwoorden.

2. **`REPO_LOCATIES` breekt het patroon.** Elke andere bron gebruikt `<BRON>_<VELD>`:
   `NEXTCLOUD_BASE_URL`, `JIRA_API_TOKEN`, `MIRO_API_TOKEN`, `WEBSITE_URLS`. Alleen Drive en
   Planning wijken af met `AUDIT_*`, en dat zijn de oudste twee — geen reden om de fout te
   herhalen.

De oude namen blijven één ronde werken en migreren zichzelf, zodat een ingevulde configuratie
niet stilvalt door een hernoeming.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from iso_audit.api.bron_catalogus import catalogus

BOTSEND = {
    "GITHUB_TOKEN": "GitHub Actions zet deze naam zelf in elke workflow",
    "GH_TOKEN": "de gh-CLI leest deze naam",
    "HOME": "systeemvariabele",
    "PATH": "systeemvariabele",
}


def _envnamen() -> list[tuple[str, str]]:
    return [(b.naam, v.naam) for b in catalogus() for v in b.velden]


def test_geen_enkele_naam_botst_met_een_bekende_variabele() -> None:
    for bron, env in _envnamen():
        assert env not in BOTSEND, f"{bron}: {env} — {BOTSEND.get(env)}"


def test_de_nieuwe_bronnen_gebruiken_hun_eigen_prefix() -> None:
    """`<BRON>_<VELD>`, net als Nextcloud, Jira en Miro."""
    for bron in ("repo", "website"):
        for b, env in _envnamen():
            if b == bron:
                assert env.startswith(bron.upper() + "_"), f"{bron}: {env}"


def test_elke_naam_is_een_geldige_env_naam() -> None:
    for bron, env in _envnamen():
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", env), f"{bron}: {env}"


def test_alleen_de_migratietabel_kent_de_oude_namen() -> None:
    """Een hernoeming die de helft van de code vergeet, is erger dan geen hernoeming.

    `bron_config.py` is de uitzondering: daar staat de vertaaltabel, en die moet de oude namen
    wel noemen — anders valt een ingevulde configuratie stil.
    """
    oud = ("AUDIT_REPOS", '"GITHUB_TOKEN"', '"CODEBERG_TOKEN"', '"GITHUB_APP_ID"')
    for pad in pathlib.Path("src").rglob("*.py"):
        if pad.name == "bron_config.py":
            continue
        tekst = pad.read_text(encoding="utf-8")
        for naam in oud:
            assert naam not in tekst, f"{pad}: {naam}"


def test_de_migratietabel_dekt_elke_hernoemde_naam() -> None:
    """Een vergeten regel laat precies dat ene veld stil omvallen."""
    from iso_audit.api.bron_config import HERNOEMD

    assert HERNOEMD["AUDIT_REPOS"] == "REPO_LOCATIES"
    assert HERNOEMD["GITHUB_TOKEN"] == "REPO_GITHUB_TOKEN"
    huidige = {v.naam for b in catalogus() for v in b.velden}
    for oude, nieuwe in HERNOEMD.items():
        assert nieuwe in huidige, f"{oude} wijst naar {nieuwe}, dat niet meer bestaat"


# --- migratie ---------------------------------------------------------------


def test_een_bestaande_configuratie_valt_niet_stil(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De auditor had net ingevuld; een hernoeming mag dat niet ongedaan maken.

    Via `monkeypatch` en niet rechtstreeks naar `os.environ`: deze test zette eerder echte
    variabelen die bleven staan, waarna `RepoSource()` verderop in de suite dacht dat er
    repositories geconfigureerd waren. Een test die de volgende test beïnvloedt, meet niets.
    """
    import json
    import os

    from iso_audit.api.bron_config import BronConfig

    (tmp_path / "bron_config.json").write_text(
        json.dumps(
            {
                "repo": {
                    "AUDIT_REPOS": "github:ConductionNL/*",
                    "GITHUB_TOKEN": "ghp_oud",
                    "REPO_MAX_PR": "0",
                }
            }
        ),
        encoding="utf-8",
    )
    # `os.environ` vervangen door een kopie: `naar_omgeving()` schrijft er rechtstreeks in, en
    # `monkeypatch.delenv` herstelt alleen wat monkeypatch zélf heeft gewijzigd. Zonder dit bleef
    # `REPO_LOCATIES` staan en dacht `RepoSource()` verderop in de suite dat er repositories
    # geconfigureerd waren — een test die de volgende test beïnvloedt, meet niets.
    monkeypatch.setattr(os, "environ", {})

    BronConfig(tmp_path, omgeving={}).naar_omgeving()
    assert os.environ.get("REPO_LOCATIES") == "github:ConductionNL/*"
    assert os.environ.get("REPO_GITHUB_TOKEN") == "ghp_oud"
    assert os.environ.get("REPO_MAX_PR") == "0"


def test_een_nieuwe_naam_wint_van_een_oude(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staan beide er, dan is de nieuwe wat de auditor het laatst bedoelde."""
    import json
    import os

    from iso_audit.api.bron_config import BronConfig

    (tmp_path / "bron_config.json").write_text(
        json.dumps({"repo": {"AUDIT_REPOS": "oud", "REPO_LOCATIES": "nieuw"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(os, "environ", {})
    BronConfig(tmp_path, omgeving={}).naar_omgeving()
    assert os.environ.get("REPO_LOCATIES") == "nieuw"
