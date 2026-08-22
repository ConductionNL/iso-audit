"""Documenten die dit tool zelf heeft voortgebracht, herkennen en niet als bewijs tellen.

## Waarom dit bestaat

Gemeten op 2026-08-22 op de eerste volledige run: **462 van de 1241 bevindingen (37%) waren
afgeleid uit twaalf documenten die dit tool zelf schreef.** Hetzelfde auditrapport in md, docx,
html én pdf; dezelfde bevindingenlijst in csv en xlsx; drie eigen managementmemo's. Ze staan in
Drive en worden als bewijs teruggelezen.

Een bevinding die als bewijs een eerder eigen auditrapport aanwijst, is geen onafhankelijke
observatie maar een echo. Voor ISO 27001 raakt dat de onafhankelijkheid van de interne
auditfunctie, en dat is precies waar een certificerende instantie op doorvraagt.

Belangrijk onderscheid: een auditrapport van de **certificerende instantie** is wél bewijs — dat
is een externe waarneming. De grens is niet "rapport" maar "van ons of van hen".

## Waarom een merkteken in de tekst en geen bestandsnaam

Op naam filteren faalt twee kanten op. Een naam wijzigt (`Auditrapport def.docx`) en het
document telt stil weer mee. En `Auditrapport 2022.docx` staat in het landschap, is van de
certificerende instantie, en moet gewoon meetellen.

Het merkteken staat daarom **als zichtbare regel in het document zelf**. Zichtbaar en niet als
HTML-commentaar, om één reden: het rapport wordt van markdown naar docx, html en pdf
geconverteerd, en alleen zichtbare tekst overleeft alle drie. Een comment sneuvelt in de
pdf-render, en dan is het merkteken er precies niet meer waar het nodig is.
"""

from __future__ import annotations

from typing import Any

MERKTEKEN = "Gegenereerd door iso-audit — geen onafhankelijk auditbewijs"
"""De regel die dit tool in zijn eigen output zet.

Zichtbaar in het document, in het Nederlands en zonder opmaak: hij moet leesbaar zijn voor wie
het rapport in handen krijgt, en herkenbaar na een conversie naar docx, html of pdf. Wie hem
weghaalt, laat het document weer meetellen — dat is een handeling, geen ongeluk."""

BESTAANDE_EIGEN_OUTPUT: frozenset[str] = frozenset(
    {
        "Auditmemo_management_2026-05-06",
        "Auditmemo_management_2026-05-06_v3.pdf",
        "Auditmemo_management_2026-06-23.pdf",
        "Auditrapport_beide_2026-03-24_s05.md",
        "Auditrapport_beide_v3.3_2026-05-05.docx",
        "Auditrapport_beide_v3.3_2026-05-05.html",
        "Auditrapport_beide_v3.3_2026-05-05.md",
        "Auditrapport_beide_v3.3_2026-05-05.pdf",
        "Bevindingen_beide_v3.3_2026-05-05.csv",
        "Bevindingen_beide_v3.3_2026-05-05.xlsx",
    }
)
"""Eenmalige lijst van bestanden die er op 2026-08-22 al stonden, vóór het merkteken bestond.

**Een lijst en geen patroon**, met opzet. Een regel als "alles wat begint met `Auditrapport_`"
zou ook `Auditrapport 2022.docx` raken — dat is het rapport van de certificerende instantie over
ons, en juist bewijs. Deze tien namen zijn één voor één nagekeken tegen de naamvorm die
`reporting.local_report.schrijf_rapport` en de memo-render produceren.

Deze lijst hoort te krimpen, niet te groeien: zodra een rapport opnieuw geschreven wordt, draagt
het het merkteken zelf en is de naam niet meer nodig. Een nieuw bestand hier toevoegen is een
signaal dat het merkteken niet werkt, geen oplossing."""

_KOPLENGTE = 4000
"""Hoeveel tekens van de tekst op het merkteken worden nagekeken.

Het merkteken staat in de kop. Een auditrapport van 200 KB helemaal doorzoeken levert alleen
valse treffers op wanneer iemand het merkteken ergens citeert."""


def is_eigen_output(*, naam: str = "", tekst: str = "") -> bool:
    """Is dit document door dit tool voortgebracht?

    Twee signalen, in deze volgorde: de eenmalige namenlijst voor wat er al stond, en het
    merkteken in de tekst — dat laatste is het bedoelde mechanisme.
    """
    if naam.strip() in BESTAANDE_EIGEN_OUTPUT:
        return True
    return MERKTEKEN in tekst[:_KOPLENGTE]


def splits(documenten: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Splits in `(extern, eigen)` — wat als bewijs telt en wat niet.

    Retourneert beide lijsten in plaats van alleen de bruikbare: de eigen output blijft in het
    landschap staan met een reden, want een auditor mag navragen waarom een document niet is
    gewogen. Zelfde regel als bij het verbergen van runs — wat uit een werklijst verdwijnt,
    blijft vindbaar.
    """
    extern: list[dict[str, Any]] = []
    eigen: list[dict[str, Any]] = []
    for doc in documenten:
        naam = str(doc.get("naam", ""))
        tekst = str(doc.get("tekst", ""))
        (eigen if is_eigen_output(naam=naam, tekst=tekst) else extern).append(doc)
    return extern, eigen
