"""Drie hiaten in de thema-toekenning, gemeten op de run van 2026-08-26.

Van 47 bevestigde NC's belandden er 10 in `Overig`. Dat is geen thema maar het ontbreken ervan:
elk zo'n bevinding krijgt in de memo een eigen blok, en tien losse blokken is precies wat een
managementmemo van drie A4 niet kan hebben.

De tien vielen in drie groepen uiteen:

1. **De clausuletitel telt niet mee.** §5.29 heet "Informatiebeveiliging en continuïteit tijdens
   verstoring van clouddiensten" en het thema "Back-up & continuïteit" heeft `continuïteit` als
   keyword — maar `bepaal_thema` las alleen beschrijving, onderbouwing en documentnaam. De
   duidelijkste samenvatting van waar de bevinding over gaat, werd genegeerd.
2. **De taxonomie mist ontwikkel- en wijzigingsbeheer.** §8.9 configuratiebeheer, §8.25 veilige
   ontwikkeling en §8.33 testinformatie horen bij elkaar en nergens anders.
3. **Toegangsbeheer kende authenticatie niet.** §5.17 (authenticatie-informatie) en §8.5 (MFA)
   zijn toegangsbeheer; de keywords stopten bij "toegangsrechten" en "autorisatie".

Wat hier bewust *niet* gebeurt: alles wegwerken. §8.7 (afwijkende procesuitvoer) en §5.5
(meldplicht autoriteiten) blijven `Overig` — daar een thema voor verzinnen om het aantal blokken
te drukken zou het cijfer verbeteren en de memo verslechteren.
"""

from __future__ import annotations

from iso_audit.classification.thema import THEMA_LIJST, bepaal_thema


def _bev(**kw: str) -> dict[str, str]:
    basis = {"beschrijving": "", "onderbouwing": "", "document_naam": "", "clausule_titel": ""}
    return {**basis, **kw}


def test_de_clausuletitel_telt_mee() -> None:
    assert (
        bepaal_thema(
            _bev(
                beschrijving="De organisatie toont dit niet aan.",
                clausule_titel="Informatiebeveiliging en continuïteit tijdens verstoring",
            )
        )
        == "Back-up & continuïteit"
    )


def test_zonder_clausuletitel_werkt_het_nog_steeds() -> None:
    """Bestaande aanroepers geven het veld niet mee; die mogen niet breken."""
    assert bepaal_thema({"beschrijving": "encryptie ontbreekt"}) == "Cryptografie & encryptie"


def test_configuratiebeheer_krijgt_een_thema() -> None:
    assert (
        bepaal_thema(_bev(beschrijving="Configuratiebeheer is niet uitgevoerd."))
        == "Ontwikkeling & wijzigingsbeheer"
    )


def test_scheiding_van_test_en_productie_krijgt_een_thema() -> None:
    assert (
        bepaal_thema(_bev(beschrijving="Testinformatie is niet gescheiden van productiegegevens."))
        == "Ontwikkeling & wijzigingsbeheer"
    )


def test_veilige_ontwikkeling_krijgt_een_thema() -> None:
    assert (
        bepaal_thema(_bev(clausule_titel="Veilige ontwikkeling van software en systemen"))
        == "Ontwikkeling & wijzigingsbeheer"
    )


def test_authenticatie_is_toegangsbeheer() -> None:
    assert (
        bepaal_thema(_bev(beschrijving="Authenticatie-informatie wordt niet beheerd."))
        == "Toegangsbeheer"
    )


def test_mfa_is_toegangsbeheer() -> None:
    assert bepaal_thema(_bev(beschrijving="MFA is niet gedefinieerd.")) == "Toegangsbeheer"


def test_het_nieuwe_thema_staat_in_de_taxonomie() -> None:
    """`THEMA_LIJST` is bron-of-truth en gaat mee in de LLM-prompt; een regel zonder lijst-entry
    zou de heuristiek en de LLM-route uit elkaar laten lopen."""
    assert "Ontwikkeling & wijzigingsbeheer" in THEMA_LIJST
    assert THEMA_LIJST[-1] == "Overig", "Overig is de fallback en hoort achteraan"


def test_wat_geen_thema_heeft_blijft_overig() -> None:
    """Geen verzonnen thema's om het blokkenaantal te drukken."""
    assert bepaal_thema(_bev(beschrijving="Beheersing van afwijkende procesuitvoer.")) == "Overig"


def test_de_eigen_tekst_wint_van_de_clausuletitel() -> None:
    """De titel is terugval, geen gelijke.

    Toen hij gewoon meetelde, verschoven 8 NC's van "Memo & afwijkingsregistratie" naar
    "Rollen & verantwoordelijkheden" — generieke normtaal matcht eerder dan de specifieke
    bevindingstekst, en dat maakte de bundeling slechter in plaats van beter.
    """
    assert (
        bepaal_thema(
            _bev(
                beschrijving="De afwijkingsprocedure wordt niet gevolgd.",
                clausule_titel="Rollen en verantwoordelijkheden bij informatiebeveiliging",
            )
        )
        == "Memo & afwijkingsregistratie"
    )
