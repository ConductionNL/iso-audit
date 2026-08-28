"""Alleen de inhoud van een pagina telt, niet de navigatie en de voettekst.

Gemeten op 2026-08-28, na het inlezen van 137 pagina's van conduction.nl: **135 daarvan**
matchten op §5.34 (privacy). Niet omdat ze over privacy gaan, maar omdat in de voettekst van elke
pagina "© 2026 Privacy · Terms · ISO" staat, en in de navigatie "Apps Solutions Academy Support
About".

Dat is geen kleine onzuiverheid. Een clausule-koppeling die op boilerplate matcht, levert
honderd bevindingen op over een eis waar de pagina niets over zegt — en dan is de dekking een
getal dat niets betekent. Precies de soort stille onwaarheid waar dit tool bevindingen over
schrijft.

`<main>` is de inhoud, `<nav>` en `<footer>` zijn dat niet. Heeft een pagina geen `<main>`, dan
valt het terug op de hele body minus nav en footer: liever te veel dan niets, want een lege
pagina leest als "hier staat niets" terwijl er wel degelijk iets stond.
"""

from __future__ import annotations

from iso_audit.sources.website import zichtbare_tekst

_PAGINA = """<html><body>
<nav>Apps Solutions Academy Support About</nav>
<main><h1>Over ons</h1><p>Wij bouwen open source.</p></main>
<footer>© 2026 Privacy · Terms · ISO 9001:2015</footer>
</body></html>"""


def test_de_navigatie_telt_niet_mee() -> None:
    assert "Solutions" not in zichtbare_tekst(_PAGINA)


def test_de_voettekst_telt_niet_mee() -> None:
    """Hier zat de fout: "Privacy" in de footer maakte 135 pagina's tot privacybewijs."""
    tekst = zichtbare_tekst(_PAGINA)
    assert "Privacy" not in tekst
    assert "9001" not in tekst


def test_de_inhoud_blijft_staan() -> None:
    assert zichtbare_tekst(_PAGINA) == "Over ons Wij bouwen open source."


def test_zonder_main_valt_het_terug_op_de_body() -> None:
    """Liever te veel dan niets: een lege pagina leest als "hier staat niets"."""
    zonder = "<html><body><nav>Menu</nav><p>De inhoud.</p><footer>Privacy</footer></body></html>"
    tekst = zichtbare_tekst(zonder)
    assert "De inhoud." in tekst
    assert "Menu" not in tekst
    assert "Privacy" not in tekst


def test_script_en_style_blijven_weg() -> None:
    ruw = "<main><style>.a{color:red}</style><script>var x=1</script><p>Beleid</p></main>"
    assert zichtbare_tekst(ruw) == "Beleid"


def test_een_pagina_zonder_structuur_levert_nog_steeds_tekst() -> None:
    assert zichtbare_tekst("<p>Kale tekst.</p>") == "Kale tekst."
