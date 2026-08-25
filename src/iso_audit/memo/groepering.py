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
    het zwaarste gezien.
    """
    per_thema: dict[str, list[Finding]] = defaultdict(list)
    los: list[Themagroep] = []
    for f in findings:
        if f.severity != "NC" or f.triage_status != "valide":
            continue
        thema = f.thema or GEEN_THEMA
        if thema == GEEN_THEMA:
            los.append(Themagroep(thema=thema, bevindingen=[f]))
            continue
        per_thema[thema].append(f)

    groepen = [Themagroep(thema=t, bevindingen=b) for t, b in per_thema.items()]
    groepen.sort(key=lambda g: (-len(g.bevindingen), g.thema))
    return groepen + los
