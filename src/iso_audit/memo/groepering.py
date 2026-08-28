"""NC's bundelen tot thema-blokken voor de managementmemo.

Het handgemaakte Q2-memo had **twee** genummerde NC's, elk met drie onderliggende bevindingen op
drie clausules: "NC 1 — Bedrijfscontinuïteit & redundantie" met §8.14, §5.29 en §5.30. De run
van 2026-08-25 leverde 91 losse NC's op, en eenennegentig blokken op drie A4 is geen memo.

Groeperen op **thema** en niet op clausule: het Q2-memo bundelt juist over clausules heen, want
daar laat één gebrek zich in meerdere eisen zien. Het thema staat al op elke bevinding
(`classification.thema.bepaal_thema`), en de review levert per clausule de kernzin die het blok
zijn synthese geeft.

Wat hier **niet** gebeurt: bevindingen weggooien of samensmelten tot één tekst. Elke bevinding
blijft zichtbaar onder zijn blok, met zijn eigen bron. Dat is wat de memo natrekbaar houdt — een
managementmemo die niet terug te voeren is op documenten, is een mening.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from iso_audit.memo.models import Finding

GEEN_THEMA = "Overig"
"""`Overig` is geen thema maar het ontbreken ervan.

Op 2026-08-24 viel 25% van de bevindingen erin. Die als één NC-blok presenteren zou suggereren
dat ze één gebrek delen, en dat is precies wat ze níet doen — dus krijgt elk zijn eigen blok."""


@dataclass
class Themagroep:
    """Eén NC-blok in de memo: meerdere bevindingen over meerdere clausules, één gebrek."""

    thema: str
    bevindingen: list[Finding] = field(default_factory=list)

    @property
    def clausules(self) -> list[str]:
        """De clausules die dit blok raakt, voor de normregel eronder."""
        return sorted({f.clause for f in self.bevindingen})

    @property
    def majors(self) -> int:
        """Hoeveel bevindingen in dit blok als `major` zijn beoordeeld.

        Bepaalt de volgorde vóór omvang: een zwaar gebrek hoort in de memo, ook als zijn thema
        klein is. Is `ernst` nergens gevuld (de review draaide niet), dan is dit overal 0 en valt
        de ordening vanzelf terug op omvang — zwaarte verzinnen zou erger zijn.
        """
        return sum(1 for f in self.bevindingen if (f.ernst or "").lower() == "major")

    @property
    def kern(self) -> str:
        """De synthese-zin van het blok — de eerste die er een heeft.

        Eén zin per blok en niet één per bevinding: het Q2-memo heeft er precies één, en drie
        varianten van dezelfde constatering onder elkaar leest als besluiteloosheid.
        """
        for f in self.bevindingen:
            if f.kern:
                return f.kern
        return ""


def groepeer_ncs(findings: list[Finding]) -> list[Themagroep]:
    """Bundel bevestigde NC's tot thema-blokken, grootste thema eerst.

    Alleen `triage_status == "valide"`: de memo bevat wat de auditor heeft bevestigd, de rest is
    nog in behandeling. Dat is de bestaande regel in `memo/builder.py` en die blijft.

    Grootste eerst omdat daar het meeste bewijs ligt; een lezer die na één blok stopt heeft dan
    het zwaarste gezien. `Overig` krijgt losse blokken achteraan.
    """
    return _groepeer(
        [f for f in findings if f.severity == "NC" and f.triage_status == "valide"],
        los_bij_geen_thema=True,
    )


def groepeer_ofis(findings: list[Finding], drempel: int) -> list[Themagroep]:
    """Bundel OFI's tot verbeterblokken: expliciet gepromote punten + thema's vanaf `drempel`.

    De drempel telt **thema's en geen clausules**. Dat is de hele reden dat deze functie bestaat:
    op de werkset van 2026-08-25 haalde geen enkele clausule de drempel van 10, terwijl de 53
    OFI's zich netjes over 16 thema's verdeelden — 7x logging & monitoring, 6x auditprogramma,
    4x back-up. Daar zitten de patronen, en een verbeteradvies gaat over een patroon.

    Een gepromote OFI trekt zijn hele thema mee: de auditor die er zelf voor tekende, wil de
    andere waarnemingen op datzelfde thema ernaast zien staan en niet los in de bijlage.

    `drempel <= 0` betekent: alleen wat expliciet gepromoveerd is. `Overig` clustert nooit — drie
    ongerelateerde punten als één verbeteradvies presenteren wekt precies de verkeerde suggestie.
    """
    ofis = [f for f in findings if f.severity == "OFI"]
    per_thema: dict[str, list[Finding]] = defaultdict(list)
    for f in ofis:
        thema = f.thema or GEEN_THEMA
        if thema != GEEN_THEMA:
            per_thema[thema].append(f)

    gekozen = [
        t
        for t, b in per_thema.items()
        if (drempel > 0 and len(b) >= drempel) or any(f.promote_to_improvement for f in b)
    ]
    groepen = [Themagroep(thema=t, bevindingen=per_thema[t]) for t in gekozen]
    groepen.sort(key=lambda g: (-len(g.bevindingen), g.thema))

    # Een gepromote OFI zonder thema hoort er ook in — anders verdwijnt een expliciete
    # auditor-keuze omdat de heuristiek geen label vond.
    los = [
        Themagroep(thema=GEEN_THEMA, bevindingen=[f])
        for f in ofis
        if f.promote_to_improvement and not f.thema
    ]
    return groepen + los


def _groepeer(findings: list[Finding], *, los_bij_geen_thema: bool) -> list[Themagroep]:
    """Bundel op thema, grootste eerst; `Overig` als losse blokken achteraan."""
    per_thema: dict[str, list[Finding]] = defaultdict(list)
    los: list[Themagroep] = []
    for f in findings:
        thema = f.thema or GEEN_THEMA
        if thema == GEEN_THEMA:
            if los_bij_geen_thema:
                los.append(Themagroep(thema=thema, bevindingen=[f]))
            continue
        per_thema[thema].append(f)

    groepen = [Themagroep(thema=t, bevindingen=b) for t, b in per_thema.items()]
    groepen.sort(key=lambda g: (-g.majors, -len(g.bevindingen), g.thema))
    return groepen + los
