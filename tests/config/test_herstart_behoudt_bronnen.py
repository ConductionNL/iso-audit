"""Een herstart mag een gekoppelde bron niet loskoppelen.

Dit is het scenario van 2026-08-24, nagebouwd: iemand vult Nextcloud in via het portaal, de
pod herstart voor een nieuwe versie, en daarna leest de bron als "niet gekoppeld" terwijl de
waarden op de PVC staan. De run-gate weigerde toen een run op een bron die volgens het
portaal wél geconfigureerd was.

De test gaat bewust door `BronConfig` + `load_config` en niet door de FastAPI-app: het gat zat
in de brug tussen die twee, en een test die de app opstart zou hem ook vinden maar niet
aanwijzen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from iso_audit.api.bron_config import BronConfig
from iso_audit.config.settings import load_config


def _configureer_en_herstart(root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Sla configuratie op, wis de omgeving zoals een herstart dat doet, en laad opnieuw.

    Het wissen is het hart van de test: `BronConfig.zet()` schrijft de waarde óók in
    `os.environ` van het lopende proces, dus zonder wissen slaagt de test op de omgeving van
    vóór de herstart en bewijst hij niets.
    """
    BronConfig(root).zet(
        "nextcloud",
        {
            "NEXTCLOUD_BASE_URL": "https://cloud.voorbeeld.nl",
            "NEXTCLOUD_USER": "audit",
            "NEXTCLOUD_APP_PASSWORD": "geheim-app-wachtwoord",
            "NEXTCLOUD_PATHS": "Beleid,Procedures",
        },
        door="auditor@voorbeeld.nl",
    )
    for naam in (
        "NEXTCLOUD_BASE_URL",
        "NEXTCLOUD_USER",
        "NEXTCLOUD_APP_PASSWORD",
        "NEXTCLOUD_PATHS",
    ):
        monkeypatch.delenv(naam, raising=False)

    verse = BronConfig(root, omgeving={})
    instellingen = load_config(root=root, ui_waarden=verse.ui_waarden(), omgeving={})
    instellingen.naar_omgeving()
    import os

    return {k: v for k, v in os.environ.items() if k.startswith("NEXTCLOUD_")}


def test_nextcloud_blijft_gekoppeld_na_herstart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    omgeving = _configureer_en_herstart(tmp_path, monkeypatch)
    assert omgeving.get("NEXTCLOUD_BASE_URL") == "https://cloud.voorbeeld.nl"
    assert omgeving.get("NEXTCLOUD_USER") == "audit"
    assert omgeving.get("NEXTCLOUD_APP_PASSWORD") == "geheim-app-wachtwoord"
    assert omgeving.get("NEXTCLOUD_PATHS") == "Beleid,Procedures"


def test_de_adapter_ziet_zichzelf_als_geconfigureerd_na_herstart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """De echte controle: niet of de env-vars er staan, maar of de bron te bouwen is.

    `NextcloudSource.__init__` zet de verbinding vast en werpt `OSError` als de omgeving de
    drie velden mist — precies de fout die de run-gate op 2026-08-24 als "niet gekoppeld"
    rapporteerde. Alleen deze kant bewijst dat de waarden ook onder de juiste namen staan.
    """
    _configureer_en_herstart(tmp_path, monkeypatch)
    from iso_audit.sources.nextcloud import NextcloudSource

    bron = NextcloudSource()  # werpt OSError als de koppeling de herstart niet overleefde
    assert bron.paden == ["Beleid", "Procedures"]
