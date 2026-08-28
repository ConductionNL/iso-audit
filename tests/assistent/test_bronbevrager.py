"""Tests voor de Bronbevrager — de bronregel is het ontwerp, dus die wordt getest.

Wat hier wordt afgedwongen is niet "het antwoord is goed" maar "het antwoord kan niet uit
iets anders komen dan het corpus". Dat is het verschil tussen een prompt die het vraagt en
code die het controleert.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from iso_audit import modellen
from iso_audit.assistent import ophalen
from iso_audit.assistent import vraag as assistent
from iso_audit.store import bewaar_assistentvraag, initialiseer, now


class _Blok:
    def __init__(self, tekst: str, soort: str = "text") -> None:
        self.type = soort
        self.text = tekst


class _Usage:
    input_tokens = 500
    output_tokens = 200
    cache_creation_input_tokens = 0
    cache_read_input_tokens = 0


class _Respons:
    def __init__(self, tekst: str, stop_reason: str = "end_turn") -> None:
        self.content = [_Blok(tekst)]
        self.stop_reason = stop_reason
        self.usage = _Usage()


class _Client:
    """Stub-client die het laatste verzoek onthoudt; geen netwerk."""

    def __init__(self, antwoord: str, stop_reason: str = "end_turn") -> None:
        self.antwoord = antwoord
        self.stop_reason = stop_reason
        self.verzoeken: list[dict[str, Any]] = []
        self.messages = self

    def create(self, **kw: Any) -> _Respons:
        self.verzoeken.append(kw)
        return _Respons(self.antwoord, self.stop_reason)


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    initialiseer(c)
    return c


def _document(c: sqlite3.Connection, doc_id: str, naam: str, tekst: str = "") -> None:
    c.execute(
        "INSERT INTO documents (id, naam, tekst, herkomst, ingested_at) VALUES (?,?,?,?,?)",
        (doc_id, naam, tekst, "Drive", now()),
    )
    c.commit()


def _koppel(c: sqlite3.Connection, doc_id: str, clausule: str, norm: str = "27001") -> None:
    c.execute(
        "INSERT INTO clause_matches (doc_id, herkomst, clausule_id, norm) VALUES (?,?,?,?)",
        (doc_id, "Drive", clausule, norm),
    )
    c.commit()


def _bevinding(
    c: sqlite3.Connection,
    doc_id: str,
    clausule: str,
    classificatie: str,
    *,
    herkomst: str = "Drive",
    naam: str = "Doc",
) -> None:
    c.execute(
        """INSERT INTO bevindingen
           (doc_id, herkomst, clausule_id, norm, classificatie, beschrijving,
            document_naam, classified_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (doc_id, herkomst, clausule, "27001", classificatie, "beschrijving", naam, now()),
    )
    c.commit()


# --- ophalen: clausule eerst ----------------------------------------------


def test_clausule_in_de_vraag_gebruikt_clause_matches_en_niet_fts(
    conn: sqlite3.Connection,
) -> None:
    """De koppeling die de pipeline legde is preciezer dan elke tekstmatch.

    Het gekoppelde document bevat het woord "encryptie" níet; via FTS was het onvindbaar.
    """
    _document(conn, "d1", "Cryptobeleid.docx", tekst="sleutelbeheer en algoritmen")
    _koppel(conn, "d1", "A.8.24")
    _document(conn, "d2", "Encryptie in de praktijk.docx", tekst="encryptie encryptie")

    corpus = ophalen.haal_bronnen_op(conn, "Welk bewijs hebben wij voor 8.24?")

    assert corpus.via_clausule is True
    doc_ids = [b.id for b in corpus.bronnen if b.soort == "document"]
    assert doc_ids == ["d1"], "alleen het gekoppelde document, niet de tekstmatch"


def test_zonder_clausule_valt_het_terug_op_fts(conn: sqlite3.Connection) -> None:
    _document(conn, "d2", "Encryptiebeleid.docx", tekst="encryptie van gegevens")

    corpus = ophalen.haal_bronnen_op(conn, "Wat hebben wij over encryptie?")

    assert corpus.via_clausule is False
    assert [b.id for b in corpus.bronnen if b.soort == "document"] == ["d2"]


def test_vraagteken_en_aanhalingstekens_breken_de_fts_query_niet(
    conn: sqlite3.Connection,
) -> None:
    """Een syntaxfout in de FTS-query zou in de UI lezen als "geen resultaten"."""
    _document(conn, "d2", "Beleid.docx", tekst="wachtwoorden")

    corpus = ophalen.haal_bronnen_op(conn, 'Wat staat er over "wachtwoorden"? (en MFA)')

    assert [b.id for b in corpus.bronnen if b.soort == "document"] == ["d2"]


def test_koppelteken_breekt_de_fts_query_niet(conn: sqlite3.Connection) -> None:
    """`non-conformiteiten` liet de route crashen met een 500.

    Gemeten in het portaal op 2026-08-24: `sqlite3.OperationalError: no such column:
    conformiteiten`. FTS5 leest het deel na het koppelteken als kolomnaam, en de vorige
    versie van `_fts_query` liet koppeltekens juist staan — de test hierboven dekte alleen
    tekens die de regex tóch al wegstript.

    Dat dit precies het kernwoord van een ISO-auditor is, is geen toeval maar de reden dat
    het opviel: elke vraag over non-conformiteiten faalde.
    """
    _document(conn, "d2", "Afwijkingen.docx", tekst="non-conformiteiten en afwijkingen")

    corpus = ophalen.haal_bronnen_op(conn, "Hoeveel non-conformiteiten hebben wij?")

    assert [b.id for b in corpus.bronnen if b.soort == "document"] == ["d2"]


@pytest.mark.parametrize(
    "vraag",
    [
        "Hoeveel non-conformiteiten zijn er?",
        "Wat staat er over multi-factor-authenticatie?",
        'Is er iets over "back-ups"?',
        "Wat zegt de norm over A.5.15 - toegangscontrole?",
        "Waar staat het beleid: encryptie?",
        "Zoek op wachtwoord* en (MFA)",
        "Wat staat er over ^toegang en NEAR-beleid?",
    ],
)
def test_geen_enkele_vraagvorm_levert_een_syntaxfout(conn: sqlite3.Connection, vraag: str) -> None:
    """Elk FTS5-operatorteken uit een mensenvraag moet onschadelijk zijn.

    Niet omdat deze vormen vaak voorkomen, maar omdat een syntaxfout hier een 500 is en geen
    leeg antwoord: de auditor ziet een kapot scherm in plaats van "niets gevonden". Het
    onderscheid tussen die twee is de hele reden dat `_documenten_via_tekst` de fout
    doorgeeft in plaats van hem als nul treffers te melden.
    """
    _document(conn, "d2", "Beleid.docx", tekst="toegangsbeleid en wachtwoorden")

    ophalen.haal_bronnen_op(conn, vraag)  # mag niet werpen


def test_operatoren_uit_de_vraag_werken_niet_als_operator(conn: sqlite3.Connection) -> None:
    """`AND` in een vraag is een woord, geen FTS5-operator.

    Zonder aanhalingstekens rond elk woord zou "beleid AND encryptie" iets anders zoeken dan
    de gebruiker vroeg — stiller dan een syntaxfout en daarom erger.
    """
    _document(conn, "d2", "Beleid.docx", tekst="encryptie")
    _document(conn, "d3", "Ander.docx", tekst="beleid")

    corpus = ophalen.haal_bronnen_op(conn, "beleid AND encryptie")

    gevonden = sorted(b.id for b in corpus.bronnen if b.soort == "document")
    assert gevonden == ["d2", "d3"], "AND werd als operator gelezen in plaats van als woord"


def test_opvolgpunten_komen_als_eigen_soort_en_niet_dubbel(conn: sqlite3.Connection) -> None:
    """Opvolgpunten staan in `bevindingen` met herkomst `<bron>-opvolging`."""
    _bevinding(conn, "ISO-709", "A.8.24", "OFI", herkomst="Jira-opvolging", naam="ISO-709")

    corpus = ophalen.haal_bronnen_op(conn, "Wat staat open op 8.24?")

    soorten = [b.soort for b in corpus.bronnen if b.soort in ("bevinding", "opvolgpunt")]
    assert soorten == ["opvolgpunt"]


def test_normtekst_gaat_mee_met_bewijslast_en_zonder_normtekst(conn: sqlite3.Connection) -> None:
    """`bewijslast` is wat deze bron bruikbaar maakt; de normtekst zelf gaat niet mee."""
    corpus = ophalen.haal_bronnen_op(conn, "Wat eist 5.1?", norm="9001")

    norm = [b for b in corpus.bronnen if b.soort == "normtekst"]
    assert norm and norm[0].id == "norm:9001:5.1"
    assert "verwacht bewijs:" in norm[0].samenvatting


def test_afkapping_wordt_geteld_en_niet_stil_weggelaten(conn: sqlite3.Connection) -> None:
    """Een lijst die stil op twaalf stopt leest als "dit is alles"."""
    for i in range(ophalen.MAX_DOCUMENTEN + 3):
        _document(conn, f"d{i}", f"Doc {i:02d}.docx")
        _koppel(conn, f"d{i}", "A.8.24")

    corpus = ophalen.haal_bronnen_op(conn, "Bewijs voor 8.24?")

    assert len([b for b in corpus.bronnen if b.soort == "document"]) == ophalen.MAX_DOCUMENTEN
    assert corpus.afgekapt["document"] >= 1


# --- geen dekking ---------------------------------------------------------


def test_vraag_zonder_dekking_levert_staat_er_niet_in(conn: sqlite3.Connection) -> None:
    """Geen bronnen betekent geen aanroep: een antwoord zonder bronnen kan niet uit de
    bronnen komen, en dat is met een `if` af te dwingen in plaats van met een verzoek."""
    client = _Client("ISO 27001 clausule 8.24 eist cryptografische beheersmaatregelen.")

    uit = assistent.beantwoord(conn, "Wat is de beste encryptiestandaard?", client=client)

    assert uit.geen_dekking is True
    assert uit.antwoord == assistent.GEEN_DEKKING
    assert client.verzoeken == [], "er mag geen model bevraagd zijn"
    assert "A.8.24" not in uit.antwoord


# --- verwijzingscontrole --------------------------------------------------


def test_antwoord_met_onbekend_bron_id_is_een_storing(conn: sqlite3.Connection) -> None:
    """ "Alleen uit de meegegeven bronnen" is een instructie; dit is de controle."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Er is beleid [bron:d-verzonnen].")

    with pytest.raises(assistent.AntwoordOnverifieerbaarError, match="niet zijn meegegeven"):
        assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)


def test_antwoord_zonder_verwijzing_wordt_vervangen(conn: sqlite3.Connection) -> None:
    """Niet weigeren en niet waarschuwen: vervangen.

    Weigeren liet een eerlijk "dit staat er niet in" falen. Een merkteken dat het model moet
    zetten werkte zolang het zich eraan hield — en dat deed het niet. Vervangen dekt beide
    gevallen tegelijk en hangt niet af van medewerking van het model.
    """
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Ja, dat is allemaal netjes geregeld.")

    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert uit.antwoord == assistent.ONVERIFIEERBAAR
    assert uit.onverifieerbaar is True
    assert "netjes geregeld" not in uit.antwoord, "de prose van het model bereikt de auditor niet"
    assert uit.ruw_antwoord == "Ja, dat is allemaal netjes geregeld.", "wél in de trail"


def test_antwoord_met_niet_meegegeven_clausule_is_een_storing(conn: sqlite3.Connection) -> None:
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Zie het beleid [bron:d1]; dit raakt ook 5.37.")

    with pytest.raises(assistent.AntwoordOnverifieerbaarError, match="clausules"):
        assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)


def test_afgekapt_antwoord_is_een_storing(conn: sqlite3.Connection) -> None:
    """Bij afkapping verdwijnt juist de bronvermelding aan het eind."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Er is beleid [bron:d1]", stop_reason="max_tokens")

    with pytest.raises(assistent.AntwoordOnverifieerbaarError, match="afgekapt"):
        assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)


def test_geldig_antwoord_geeft_gebruikte_bronnen_terug(conn: sqlite3.Connection) -> None:
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Het cryptobeleid raakt 8.24 [bron:d1] [bron:d1].")

    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert uit.gebruikt == ["d1"], "zonder duplicaten"
    assert uit.model == modellen.STANDAARD
    assert uit.usd > 0
    assert uit.grondslag and uit.peildatum


def test_thinking_staat_expliciet_uit(conn: sqlite3.Connection) -> None:
    """Weglaten maakt het gedrag afhankelijk van het model; dat kostte op 2026-08-17 stil
    nul bevindingen op twee van de drie modellen."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Beleid [bron:d1].")

    assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert client.verzoeken[0]["thinking"] == {"type": "disabled"}
    assert client.verzoeken[0]["max_tokens"] == assistent.MAX_TOKENS


# --- tegenspraak ----------------------------------------------------------


def test_tegenspraak_levert_beide_bronnen(conn: sqlite3.Connection) -> None:
    """Een document dat dekking claimt naast een NC op dezelfde clausule: beide gaan mee,
    en de assistent kiest niet. Een regel als "nieuwste wint" verbergt precies die
    spanning."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    _bevinding(conn, "d1", "A.8.24", "NC", naam="Cryptobeleid.docx")

    corpus = ophalen.haal_bronnen_op(conn, "Zijn wij in orde op 8.24?")

    soorten = {b.soort for b in corpus.bronnen}
    assert {"document", "bevinding"} <= soorten
    prompt = assistent._user_prompt("Zijn wij in orde op 8.24?", corpus)
    assert "Cryptobeleid.docx" in prompt and "NC op A.8.24" in prompt


def test_de_prompt_benoemt_tegenspraak_als_geldige_uitkomst() -> None:
    """Zonder dat lost het model het stil op door één bron te negeren."""
    assert "TEGENSPRAAK" in assistent.SYSTEEM
    assert "kiest niet" in assistent.SYSTEEM
    assert "geen bevinding" in assistent.SYSTEEM


# --- schrijft niets -------------------------------------------------------


def test_de_assistent_schrijft_geen_bevinding_en_geen_besluit(conn: sqlite3.Connection) -> None:
    """De auditor-spiegel is de capability die dit tool draagt: een mens houdt het oordeel."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Beleid [bron:d1].")

    assistent.beantwoord(conn, "Is dit een afwijking op 8.24?", client=client)

    assert conn.execute("SELECT COUNT(*) FROM bevindingen").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0


# --- trail ----------------------------------------------------------------


def test_vraag_en_antwoord_staan_met_de_meegegeven_bronnen_in_de_trail(
    conn: sqlite3.Connection,
) -> None:
    """Een antwoord dat achteraf verkeerd blijkt is alleen te begrijpen als je weet wat de
    assistent op dat moment kon zien."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Beleid [bron:d1].")
    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    rij_id = bewaar_assistentvraag(
        conn, agent="bronbevrager", record=uit.als_record(), gesteld_door="a@b.c"
    )

    conn.row_factory = sqlite3.Row
    rij = conn.execute("SELECT * FROM assistent_vragen WHERE id = ?", (rij_id,)).fetchone()
    assert rij["vraag"] == "Bewijs voor 8.24?"
    assert "d1" in rij["meegegeven_json"]
    assert "d1" in rij["gebruikt_json"]
    assert rij["model"] == modellen.STANDAARD
    assert rij["prijzen_grondslag"] and rij["prijzen_peildatum"]
    assert rij["gesteld_door"] == "a@b.c"


def test_storing_wordt_ook_vastgelegd(conn: sqlite3.Connection) -> None:
    """Het enige spoor dat de verwijzingscontrole heeft gewerkt."""
    bewaar_assistentvraag(
        conn,
        agent="bronbevrager",
        record={"vraag": "Bewijs voor 8.24?", "antwoord": "", "model": ""},
        storing="antwoord verwijst naar bronnen die niet zijn meegegeven: d-verzonnen",
    )

    conn.row_factory = sqlite3.Row
    rij = conn.execute("SELECT * FROM assistent_vragen").fetchone()
    assert rij["antwoord"] == ""
    assert "niet zijn meegegeven" in rij["storing"]


# --- "staat er niet in" met de reden erbij --------------------------------
#
# De eerste echte vraag in het portaal (2026-08-21) was "welk bewijs hebben we voor 8.2.4?".
# Die clausule bestaat niet in ISO 27001:2022 — Annex A kent 8.24, en daar hingen 24
# documenten aan. De assistent antwoordde correct "staat er niet in" en verzweeg daarmee dat
# de clausule zélf niet bestaat.


def test_niet_bestaande_clausule_wordt_als_zodanig_gemeld(conn: sqlite3.Connection) -> None:
    corpus = ophalen.haal_bronnen_op(conn, "Welk bewijs hebben we voor 8.2.4?")

    assert corpus.onbekende_clausules == ("8.2.4",)
    assert corpus.suggesties["8.2.4"] == ["A.8.24"], "zelfde cijferreeks zonder punten"
    tekst = assistent.geen_dekking_tekst(corpus, "27001")
    assert "bestaat niet in ISO 27001" in tekst
    assert "A.8.24" in tekst


def test_suggestie_is_een_cijfervergelijking_en_geen_drempel() -> None:
    """Geen gelijkenis-maat: "0.83 leek genoeg" is geen antwoord aan een auditor."""
    assert ophalen.gelijkende_clausules("8.2.4", "27001") == ["A.8.24"]
    assert ophalen.gelijkende_clausules("8.99", "27001") == []
    assert ophalen.gelijkende_clausules("A.8.24", "27001") == [], "zichzelf niet suggereren"


def test_bestaande_clausule_zonder_bewijs_is_geen_lege_uitkomst(
    conn: sqlite3.Connection,
) -> None:
    """Een clausule die de norm kent maar waar niets aan gekoppeld is, is een dekkingsgat —
    een auditbevinding in de dop, geen "staat er niet in"."""
    corpus = ophalen.haal_bronnen_op(conn, "Welk bewijs hebben we voor 8.24?")

    assert corpus.onbekende_clausules == ()
    assert not corpus.is_leeg(), "de normtekst met bewijslast gaat mee"
    assert [b.soort for b in corpus.bronnen] == ["normtekst"]


def test_zonder_clausule_blijft_de_algemene_tekst(conn: sqlite3.Connection) -> None:
    corpus = ophalen.haal_bronnen_op(conn, "Wat hebben wij over sleutelbeheer?")

    assert assistent.geen_dekking_tekst(corpus, "27001") == assistent.GEEN_DEKKING


# --- eerlijk "niet gevonden" is geen storing ------------------------------
#
# Gemeten op 2026-08-22 tegen het echte corpus: van drie vragen gaf één een antwoord met 25
# bronnen en kwamen twee terug als 502 met "antwoord bevat geen enkele bronverwijzing". Dat
# was niet het model dat iets verzon — het zei correct dat het gevraagde niet in díe bronnen
# stond, en had daarmee niets om naar te verwijzen. De controle weigerde een eerlijk antwoord.


def test_leeg_corpus_en_onverifieerbaar_zijn_twee_verschillende_dingen(
    conn: sqlite3.Connection,
) -> None:
    """Geen bronnen gevonden is iets anders dan bronnen die de vraag niet beantwoorden.

    Het eerste bevraagt geen model; het tweede wel, en het antwoord blijkt dan niet na te
    trekken. Beide teksten zeggen iets anders tegen de auditor.
    """
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")

    leeg = assistent.beantwoord(conn, "Wat is de beste encryptie?", client=_Client("x"))
    assert leeg.geen_dekking is True and leeg.onverifieerbaar is False

    met_bronnen = assistent.beantwoord(
        conn, "Staat er iets over catering in 8.24?", client=_Client("Nee, niets.")
    )
    assert met_bronnen.geen_dekking is False and met_bronnen.onverifieerbaar is True


def test_eerlijk_niet_gevonden_levert_dezelfde_vaste_tekst(conn: sqlite3.Connection) -> None:
    """Een eerlijk "niet gevonden" en een bewering uit modelkennis komen op hetzelfde neer.

    Beide zijn niet na te trekken, dus beide leveren de vaste tekst. Dat is het punt: het
    onderscheid is van buitenaf niet te maken, dus het tool doet alsof het dat kan.
    """
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client(f"Hierover staat niets in de bronnen. {assistent.NIETS_GEVONDEN}")

    uit = assistent.beantwoord(conn, "Staat er iets over catering in 8.24?", client=client)

    assert uit.antwoord == assistent.ONVERIFIEERBAAR
    assert uit.onverifieerbaar is True


def test_verzonnen_bron_blijft_een_storing(conn: sqlite3.Connection) -> None:
    """Vervangen geldt voor geen verwijzing; een verzónnen verwijzing blijft geweigerd."""
    _document(conn, "d1", "Cryptobeleid.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client(f"Niets gevonden {assistent.NIETS_GEVONDEN}, zie wel [bron:d-verzonnen].")

    with pytest.raises(assistent.AntwoordOnverifieerbaarError, match="niet zijn meegegeven"):
        assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)


def test_de_prompt_noemt_het_merkteken_en_de_vervanging() -> None:
    assert assistent.NIETS_GEVONDEN in assistent.SYSTEEM
    assert "vervangen" in assistent.SYSTEEM


def test_meerdere_bronnen_in_een_merkteken(conn: sqlite3.Connection) -> None:
    """Het model schrijft `[bron:a, b, c]` als een bewering op meerdere documenten rust.

    Gemeten op 2026-08-22 tegen het echte corpus: twaalf geldige ID's plus een normtekst
    werden als één onbekend ID gelezen, en een geldig antwoord werd geweigerd als verzonnen.
    """
    for i in (1, 2, 3):
        _document(conn, f"d{i}", f"Doc {i}.docx")
        _koppel(conn, f"d{i}", "A.8.24")
    client = _Client("De rapporten dekken dit [bron:d1, d2,  d3].")

    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert uit.gebruikt == ["d1", "d2", "d3"], "gesplitst en gestript, volgorde behouden"


def test_een_onbekend_id_in_een_groep_blijft_een_storing(conn: sqlite3.Connection) -> None:
    """Tolerant voor de vorm, niet voor de inhoud: élk los ID moet meegegeven zijn."""
    _document(conn, "d1", "Doc 1.docx")
    _koppel(conn, "d1", "A.8.24")
    client = _Client("Zie [bron:d1, d-verzonnen].")

    with pytest.raises(assistent.AntwoordOnverifieerbaarError, match="d-verzonnen"):
        assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)


def test_bronnen_gescheiden_door_het_woord_en(conn: sqlite3.Connection) -> None:
    """Het model antwoordt in het Nederlands en schrijft `[bron:a en b]`.

    Gemeten tegen het echte corpus op 2026-08-22, nadat de komma-splitsing al was gerepareerd:
    twee geldige ID's werden als één onbekend ID geweigerd.
    """
    for i in (1, 2):
        _document(conn, f"d{i}", f"Doc {i}.docx")
        _koppel(conn, f"d{i}", "A.8.24")
    client = _Client("Beide rapporten dekken dit [bron:d1 en d2].")

    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert uit.gebruikt == ["d1", "d2"]


def test_herhaald_bron_voorvoegsel_binnen_een_merkteken(conn: sqlite3.Connection) -> None:
    """Het model schrijft `[bron:a, bron:b]` — het voorvoegsel herhaald binnen één merkteken.

    Derde vormvariant die pas tegen het echte model boven water kwam, na de komma-lijst en het
    woord "en". Elke keer geldige verwijzingen die als verzonnen werden geweigerd.
    """
    for i in (1, 2):
        _document(conn, f"d{i}", f"Doc {i}.docx")
        _koppel(conn, f"d{i}", "A.8.24")
    client = _Client("Zie [bron:d1, bron:d2].")

    uit = assistent.beantwoord(conn, "Bewijs voor 8.24?", client=client)

    assert uit.gebruikt == ["d1", "d2"]


def test_een_id_met_en_erin_valt_niet_uiteen() -> None:
    """Woordgrenzen: `1eDQv1pQ8r2Sv...` bevat "en" maar is één ID — die bestaat echt."""
    assert assistent._bron_ids("[bron:1eDQv1pQ8r2SvfPmizc6-KG2MHGnFgNwS]") == [
        "1eDQv1pQ8r2SvfPmizc6-KG2MHGnFgNwS"
    ]


def test_bron_ids_negeert_lege_stukken() -> None:
    assert assistent._bron_ids("[bron:a, , b]") == ["a", "b"]
    assert assistent._bron_ids("[bron:a; b & c]") == ["a", "b", "c"]
    assert assistent._bron_ids("[bron: a ][bron:a]") == ["a"], "dubbel telt één keer"
    assert assistent._bron_ids("geen merkteken") == []
