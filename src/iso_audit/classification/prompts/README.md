# Classificatie-prompts

Versiegestuurd op schijf en niet in de code, omdat de prompt bepaalt of iets een NC of een OFI
wordt. `classifications.prompt_versie` bewaart een sha256 van de gebruikte systeemprompt; met
deze bestanden erbij is achteraf niet alleen te zien **dát** de prompt veranderde maar ook wat
er stond.

| bestand | wanneer |
|---|---|
| `v2-scherp.md` | `--scherpte >= 0.75` (standaard) |
| `v2-genuanceerd.md` | `--scherpte < 0.75` |
| `v2-miro.md` | Miro-notities |

Klantspecifieke jurisprudentie hoort **niet** in deze bestanden maar in het profiel: wat bij
Conduction geldt (BYOD, "memo is sluitingsbewijs") is bij de volgende klant onjuist.
