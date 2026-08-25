"""`beoordeel()` respecteert de schakelaar en laat één storing de rest niet stoppen."""

from __future__ import annotations

from typing import Any

from iso_audit.classification.review import Clausulegroep, ReviewInstelling, beoordeel

_MODEL = "claude-haiku-4-5"


class _Weigeraar:
    """Elke aanroep is een fout: zo bewijst de test dat er niet is aangeroepen."""

    def __getattr__(self, naam: str) -> Any:
        raise AssertionError("er mag geen model bevraagd zijn")


def _groep(clausule: str, klasse: str = "NC") -> Clausulegroep:
    return Clausulegroep(
        clausule=clausule,
        norm="27001",
        bevindingen=[
            {
                "doc_id": "d1",
                "document_naam": "Beleid.docx",
                "classificatie": klasse,
                "beschrijving": "Iets",
                "onderbouwing": "§" + clausule,
            }
        ],
    )


def test_uit_betekent_geen_aanroep() -> None:
    uit = ReviewInstelling(aan=False, herkomst="standaard")
    assert beoordeel([_groep("8.16")], instelling=uit, model=_MODEL, client=_Weigeraar()) == []


def test_steekproef_kapt_af_op_de_zwaarste() -> None:
    """De groepen staan op zwaarte; een steekproef pakt dus de NC's eerst."""
    aangeroepen: list[str] = []

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def stream(**kw: Any) -> Any:
                aangeroepen.append(kw["messages"][0]["content"])
                raise RuntimeError("gestopt na registratie")

    aan = ReviewInstelling(aan=True, herkomst="vlag")
    groepen = [_groep("8.16"), _groep("5.1", "OFI"), _groep("4.1", "positief")]
    uitkomsten = beoordeel(groepen, instelling=aan, model=_MODEL, steekproef=1, client=_Client())
    assert len(uitkomsten) == 1
    assert "§8.16" in aangeroepen[0]


def test_een_storing_stopt_de_rest_niet() -> None:
    beurten: list[int] = []

    class _Client:
        class messages:  # noqa: N801
            @staticmethod
            def stream(**kw: Any) -> Any:
                beurten.append(1)
                raise RuntimeError("stuk")

    aan = ReviewInstelling(aan=True, herkomst="vlag")
    uitkomsten = beoordeel(
        [_groep("8.16"), _groep("5.1")], instelling=aan, model=_MODEL, client=_Client()
    )
    assert len(beurten) == 2
    assert all(storing for _, _, storing in uitkomsten)
    assert all(advies is None for _, advies, _ in uitkomsten)
