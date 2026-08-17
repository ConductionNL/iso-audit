# Design — landschap-dekking

## In drie lagen, van gratis naar duur

De 213 ongelezen bestanden zijn niet één probleem. De volgorde waarin ze worden opgelost is
de volgorde van kosten en risico:

**Laag 1 — een MIME-regel erbij, geen code die iets kan breken.** `text/markdown`,
`text/html` en `text/csv` zijn pure tekst; ze worden overgeslagen omdat de lijst alleen
`text/plain` kent. Zes bestanden, waaronder een auditrapport.

**Laag 2 — bestaande afhankelijkheden.** `openpyxl` (`.xlsx`, 23), `python-pptx` (`.pptx`, 2)
en de Drive-export voor Google Sheets (21) en Slides (19). Niets nieuws in `uv.lock`.

**Laag 3 — één nieuwe afhankelijkheid.** PDF, 91 bestanden en de auditkritische kern. Zie
hieronder.

Die volgorde is geen procesnetheid: laag 1 en 2 leveren 71 bestanden op zonder één nieuwe
regel in de lockfile, en die winst hoeft niet te wachten op de afweging over laag 3.

## PDF: welke bibliotheek, en waarom dat een afweging is

De repo heeft nu geen PDF-lezer. `weasyprint` schrijft PDF's maar leest ze niet.

Voorstel: `pypdf` — pure Python, geen systeembibliotheken, breed gebruikt. Alternatief is
`pdfplumber`, dat betere tabelherkenning heeft maar `pdfminer.six` meebrengt en zwaarder is.
Voor auditdocumenten is doorlopende tekst het belangrijkst, niet tabelstructuur; `pypdf` is
de saaiere keuze.

Deze toevoeging valt onder de supply-chain-discipline uit `~/.claude/CLAUDE.md`: `uv add`,
`uv.lock` gecommit, en de lockfile-diff reviewen op onverwachte resolved-URL's vóór de
commit. Een nieuwe afhankelijkheid in een repo die zelf onder ISO 27001-scope valt, is een
beslissing en geen bijvangst.

## Snelkoppelingen: volgen, en één keer tellen

Een Drive-snelkoppeling heeft `mimeType: application/vnd.google-apps.shortcut` en
`shortcutDetails.targetId` plus `targetMimeType`. Die velden staan **niet** in `_LIJST_VELDEN`
en moeten erbij.

De dedup in `list_documents` werkt al op file-id, en dat is precies wat hier nodig is: een
snelkoppeling naar een document dat óók rechtstreeks in scope zit, mag niet twee keer
meetellen. Het doel-ID gaat dus door dezelfde `gezien`-set.

Wat een snelkoppeling naar iets buiten de gekoppelde locaties betreft: die wordt gevolgd. Dat
is het punt van een snelkoppeling, en de auditor die hem aanmaakte bedoelde dat het document
in scope hoort.

## Leeg is niet leeg: het onderscheid dat deze change moet maken

Een gescande PDF levert nul tekens tekst op. Zonder onderscheid komt hij als document met
lege inhoud in het landschap, en classificeert de pipeline hem als "geen bewijs" — wat een
oordeel is over een document dat niemand heeft gelezen.

Drie uitkomsten, drie behandelingen:

| uitkomst | behandeling |
|---|---|
| tekst gevonden | gewoon document |
| bestand gelezen, nul tekst | **niet als document opnemen**; melden als "onleesbaar, mogelijk gescand" |
| type niet ondersteund | melden per categorie, met aantal |

Dat tweede geval is dezelfde regel die vandaag bij de classificatie is ingevoerd: een leeg
resultaat uit een geslaagde bewerking is een storing, geen uitkomst. Hier is de inzet groter,
want een lege inhoud die wél als document telt, geeft een NC op een clausule waar het bewijs
gewoon bestaat maar niet gelezen is.

## Dekking in het run-record, niet alleen in het log

Het run-record krijgt een `dekking`-blok: gezien, gelezen, en per reden het aantal
overgeslagen bestanden.

Waarom in het record en niet in het log: het log verdwijnt bij een podherstart, en de vraag
"welk deel van de bron heeft het tool gezien" is precies wat een certificerende instantie
stelt. Dezelfde redenering als bij de kosten, die vandaag om die reden van het log naar het
run-record zijn verhuisd.

Vorm: aantallen per reden, niet per bestand. Een lijst van 213 namen in elk run-record maakt
de trail onleesbaar; de namen staan al in het handmatige-review-spoor.

## Wat dit kost aan classificatie

Meer documenten is meer classificaties. Bij de op 2026-08-17 gemeten tarieven —
$0,00133 (Haiku) tot $0,01145 (Opus 5) per classificatie — kost een verdubbeling van het
landschap enkele euro's per audit. Geen bezwaar, wel iets om te noemen in de change die de
dekking vergroot in plaats van het als verrassing te laten opduiken.
