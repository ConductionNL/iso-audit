"""De repobron levert één document per bewijssoort, niet één per repository.

De A.5-run van 2026-08-29 gaf 137 bevindingen uit repository's, waarvan 47 op A.5.32 die allemaal
hetzelfde zeiden: "deze repository heeft een LICENSE-bestand". Dat is geen 47 keer bewijs maar
één constatering over 47 repository's — en in een memo van 1-3 A4 onbruikbaar. Het kostte
bovendien 1.369 modelaanroepen en $4,33.

Een auditor stelt de vraag per **maatregel**: "is het intellectueel eigendom geregeld?" Het
antwoord daarop is "95 van de 386 repository's hebben een licentiebestand", niet vijfennegentig
losse constateringen.

Wat níet verdwijnt is de natrekbaarheid: het aggregaat noemt de repository's die het betreft, en
de inhoud van de bestanden gaat ontdubbeld mee — 128 SECURITY.md's zijn in de praktijk een
handvol varianten van hetzelfde sjabloon, en dat verschil is nu juist wat een auditor wil zien.
"""

from __future__ import annotations

from typing import ClassVar

from iso_audit.clients.forge import Bestand, Repositoriegegevens, Wijzigingen
from iso_audit.sources.repo import RepoSource


class _Org:
    """Drie repository's: twee met een licentie, één zonder; twee identieke SECURITY.md's."""

    forge = "github"
    INHOUD: ClassVar[dict[tuple[str, str], str]] = {
        ("een", "LICENSE"): "EUPL-1.2",
        ("twee", "LICENSE"): "EUPL-1.2",
        ("een", "SECURITY.md"): "Meld kwetsbaarheden via security@example.org",
        ("twee", "SECURITY.md"): "Meld kwetsbaarheden via security@example.org",
        ("drie", "SECURITY.md"): "Andere tekst met een ander adres",
    }

    def repositories(self, eigenaar: str) -> tuple[list[str], str]:
        return ["een", "twee", "drie"], ""

    def repository(self, eigenaar: str, naam: str) -> Repositoriegegevens:
        return Repositoriegegevens(
            naam=f"{eigenaar}/{naam}",
            forge="github",
            url="",
            prive=False,
            gearchiveerd=False,
            hoofdbranch="main",
            branch_beschermd=naam == "een",
            review_verplicht=naam == "een",
            gewijzigd=f"2026-08-{20 + len(naam)}T10:00:00Z",
        )

    def paden(self, eigenaar: str, naam: str) -> tuple[list[str], str]:
        return [p for (r, p) in self.INHOUD if r == naam], ""

    def bestand(self, eigenaar: str, naam: str, pad: str) -> Bestand:
        return Bestand(pad=pad, inhoud=self.INHOUD[(naam, pad)])

    def bestanden_in_map(self, e: str, n: str, m: str) -> tuple[list[str], str]:
        return [], ""

    def wijzigingen(self, e: str, n: str, a: int) -> Wijzigingen:
        return Wijzigingen()


def _bron() -> RepoSource:
    bron = RepoSource([{"forge": "github", "eigenaar": "Org", "naam": "*"}])
    bron._clients["github"] = _Org()  # type: ignore[assignment]
    return bron


def test_er_komt_een_document_per_bewijssoort_en_niet_per_repository() -> None:
    docs = list(_bron().list_documents())
    assert len(docs) <= 4, [d.titel for d in docs]
    paden = {d.inhoud_uri.split("#", 1)[1] for d in docs}
    assert paden == {"instellingen", "LICENSE", "SECURITY.md"}


def test_het_aggregaat_telt_aanwezig_en_afwezig() -> None:
    bron = _bron()
    doc = next(d for d in bron.list_documents() if d.inhoud_uri.endswith("#LICENSE"))
    tekst = bron.fetch_content(doc)
    assert "2 van de 3" in tekst
    assert "drie" in tekst, "de repository zonder licentie moet met naam genoemd worden"


def test_identieke_inhoud_wordt_ontdubbeld() -> None:
    """128 SECURITY.md's zijn in de praktijk een handvol varianten van hetzelfde sjabloon."""
    bron = _bron()
    doc = next(d for d in bron.list_documents() if d.inhoud_uri.endswith("#SECURITY.md"))
    tekst = bron.fetch_content(doc)
    assert tekst.count("security@example.org") == 1, "dezelfde tekst hoort er één keer in"
    assert "Andere tekst" in tekst, "een afwijkende variant is juist interessant"


def test_de_instellingen_worden_geteld_en_niet_herhaald() -> None:
    """ "1 van de 3 repository's stelt review verplicht" is de bevinding, geen drie regels."""
    bron = _bron()
    doc = next(d for d in bron.list_documents() if d.inhoud_uri.endswith("#instellingen"))
    tekst = bron.fetch_content(doc)
    assert "1 van de 3" in tekst
    assert "twee" in tekst and "drie" in tekst, "de repository's zonder review moeten erin staan"


def test_het_aggregaat_draagt_de_laatste_wijzigingstijd() -> None:
    """Anders kan de incrementele ingest het nooit overslaan — zie `splits_op_leeftijd`."""
    docs = list(_bron().list_documents())
    assert all(d.laatst_gewijzigd for d in docs), [(d.titel, d.laatst_gewijzigd) for d in docs]
    assert max(d.laatst_gewijzigd for d in docs) == "2026-08-24T10:00:00Z"


def test_de_clausulekoppeling_blijft_werken() -> None:
    """Het aggregaat moet nog steeds aan A.5.24 en A.5.32 hangen."""
    from iso_audit.classification.bron_clausules import voor_repo_document

    docs = list(_bron().list_documents())
    for doc in docs:
        pad = doc.inhoud_uri.split("#", 1)[1]
        assert voor_repo_document(pad), f"geen koppeling voor {pad}"
