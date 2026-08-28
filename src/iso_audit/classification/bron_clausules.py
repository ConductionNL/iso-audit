"""Vaste clausule-koppeling voor bronnen waar zoektermen niet werken.

`koppel_documenten` matcht Nederlandse normtermen op de documenttekst. Dat werkt voor beleid en
notulen, maar niet voor wat de repository- en website-bron leveren:

- Een `SECURITY.md` is Engels en bevat de woorden uit de norm niet. Hij is desondanks bewijs
  voor §8.8 — niet vanwege zijn tekst, maar vanwege *wat hij is*.
- "Branch-bescherming op de hoofdbranch: niet ingesteld" is de kern van §8.32, en er staat geen
  enkele zoekterm in.
- Een `/privacy/`-pagina raakt §5.34 ongeacht de formulering.

Voor die documenten geldt de koppeling dus op **soort**, niet op inhoud. Dat is geen tweede
mechanisme naast de zoektermen: de vaste koppeling komt erbij, de zoektermen blijven draaien.
Een `SECURITY.md` die toevallig over back-ups gaat, krijgt §8.13 er gewoon bij.

De 27001-maatregelen dragen de `A.`-prefix van Bijlage A: A.8.8 is "Beheer van technische
kwetsbaarheden", terwijl 8.8 als managementclausule niet bestaat. Elke clausule hier moet in de
norm-DB staan; `tests/classification/test_bron_clausules.py` faalt zodra dat niet zo is. Een
koppeling naar een clausule die niet bestaat, levert een bevinding op die nergens over gaat — dat
is precies de fout die op 2026-08-24 448 van de 903 bevindingen verkeerd labelde.
"""

from __future__ import annotations

from typing import Final

Koppeling = tuple[tuple[str, str], ...]
"""Paren van (clausule, normcode)."""

REPO_BESTANDEN: Final[dict[str, Koppeling]] = {
    "README.md": (("7.5", "9001"),),
    "profile/README.md": (("4.1", "9001"),),
    "SECURITY.md": (("A.8.8", "27001"), ("A.5.24", "27001")),
    "CONTRIBUTING.md": (("A.8.28", "27001"),),
    "CODEOWNERS": (("A.5.2", "27001"), ("A.8.32", "27001")),
    ".github/CODEOWNERS": (("A.5.2", "27001"), ("A.8.32", "27001")),
    "LICENSE": (("A.5.32", "27001"),),
    ".github/dependabot.yml": (("A.8.8", "27001"),),
    "renovate.json": (("A.8.8", "27001"),),
    ".pre-commit-config.yaml": (("A.8.28", "27001"),),
}
"""Welk bewijspad welke eis raakt.

§8.8 technische kwetsbaarheden, §5.24 incidentplanning (een SECURITY.md zegt waar een melding
heen gaat), §8.28 veilig programmeren, §5.2 rollen, §8.32 wijzigingsbeheer, §5.32 intellectueel
eigendom, 9001 §7.5 gedocumenteerde informatie.

`profile/README.md` — het org-profiel in `<org>/.github` — hangt aan 9001 §4.1, context van de
organisatie. Daar staat wat een organisatie publiek zegt te zijn en te maken; of dat strookt met
het interne beleid is precies wat een auditor wil kunnen leggen.

Hier wordt niets ingevuld of verondersteld: er wordt alleen gelezen wat er staat."""

REPO_WORKFLOWS: Final[Koppeling] = (
    ("A.8.25", "27001"),
    ("A.8.31", "27001"),
    ("A.8.32", "27001"),
)
"""CI-workflows: veilige ontwikkelcyclus, scheiding van omgevingen, wijzigingsbeheer."""

REPO_INSTELLINGEN: Final[Koppeling] = (
    ("A.8.4", "27001"),
    ("A.8.32", "27001"),
    ("A.5.2", "27001"),
)
"""Zichtbaarheid, branch-bescherming en de review-eis.

§8.4 toegang tot broncode, §8.32 wijzigingsbeheer, §5.2 rollen — het vier-ogen-principe is een
rolverdeling die hier wel of niet is afgedwongen."""

WEBSITE_PADEN: Final[dict[str, Koppeling]] = {
    "/about": (("4.1", "9001"),),
    "/privacy": (("A.5.34", "27001"),),
    "/terms": (("A.5.31", "27001"), ("8.2", "9001")),
    "/quality": (("A.5.1", "27001"), ("5.2", "9001")),
    "/support": (("8.2", "9001"),),
    "/contact": (("A.5.5", "27001"),),
}
"""Publieke toezeggingen per padprefix.

§5.34 privacy, §5.31 wettelijke en contractuele eisen, 9001 §8.2 eisen aan producten en
diensten, §5.1 beleid, 9001 §5.2 kwaliteitsbeleid, §5.5 contact met autoriteiten, 9001 §4.1
context van de organisatie (`/about/` — wat de organisatie publiek zegt te zijn).

Padprefix en geen volledige URL: `/privacy/` en `/privacy/cookies/` gaan over hetzelfde."""


def voor_repo_document(pad: str) -> Koppeling:
    """De vaste koppeling voor één repository-document.

    `pad` is het bewijspad, `"instellingen"` voor het metadata-document, of een workflowpad.
    Een onbekend pad levert niets op — dan blijven alleen de zoektermen over, en dat is de
    juiste uitkomst: liever geen koppeling dan een geraden koppeling.
    """
    if pad == "instellingen":
        return REPO_INSTELLINGEN
    if pad.startswith((".github/workflows/", ".forgejo/workflows/")):
        return REPO_WORKFLOWS
    return REPO_BESTANDEN.get(pad, ())


def voor_webpagina(url: str) -> Koppeling:
    """De vaste koppeling voor één webpagina, op padprefix."""
    from urllib.parse import urlparse

    pad = urlparse(url).path.rstrip("/") or "/"
    for prefix, koppeling in WEBSITE_PADEN.items():
        if pad == prefix or pad.startswith(f"{prefix}/"):
            return koppeling
    return ()


def alle_koppelingen() -> set[tuple[str, str]]:
    """Elke (clausule, norm) die hier voorkomt — voor de test tegen de norm-DB."""
    paren: set[tuple[str, str]] = set()
    for koppeling in REPO_BESTANDEN.values():
        paren.update(koppeling)
    for koppeling in WEBSITE_PADEN.values():
        paren.update(koppeling)
    paren.update(REPO_WORKFLOWS)
    paren.update(REPO_INSTELLINGEN)
    return paren
