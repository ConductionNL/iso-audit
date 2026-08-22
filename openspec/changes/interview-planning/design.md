# Design — interview-planning

## Waar de vragen vandaan komen

Uit `data/normteksten`: per clausule staan daar `interpretatie` en `bewijslast` — een lijst van
wat een externe auditor als bewijs verwacht. Die lijst is de bron van de vragen, niet
modelkennis over interviewtechniek.

Vorm: per open bewijslast-item één vraag. "Notulen directiebeoordeling waarin context is
besproken" wordt "is de context besproken in de directiebeoordeling, en waar staat dat
vastgelegd?" — een vraag die naar bewijs leidt in plaats van naar een mening.

Dat is bewust smal. Een agent die vrije interviewvragen bedenkt, verzint eisen die niet in de
norm staan, en dan staat er in een auditdossier een vraag die niemand kan herleiden.

## Rol, geen naam

De norm-catalogus kent geen personen en het tool hoort ze niet te raden. Het voorstel noemt de
rol; wie dat is, vult de auditor in. Dat is ook de plek waar het hoort: de auditor weet wie bij
Conduction over toegangsrechten gaat, en die kennis in een prompt stoppen maakt hem niet beter.

Consequentie: een voorgesteld interview is nooit direct verzendbaar. Er zit altijd één menselijke
handeling tussen — en dat is hier een feature.

## Welke clausules in aanmerking komen

Twee voorwaarden, en beide zijn nodig:

1. **Geen documentbewijs**: geen `clause_matches` voor die clausule. `interview._haal_gaps_op`
   doet dit al.
2. **Bewijslast die een mens kan bevestigen.** Niet elke ongedekte clausule vraagt een gesprek:
   voor "de VvT is vastgesteld" is een document het enige geldige bewijs, en een interview zou
   daar bewijs vervangen door een bewering.

Dat tweede vraagt een markering in de norm-catalogus per bewijslast-item: is dit een artefact of
een waarneming? Zonder die markering wordt het een agent-inschatting, en dan verschuift de
bewijsstandaard per run.

## Inplannen: één handeling, één bevestiging

De agenda-uitnodiging is de eerste keer dat dit tool iets naar buiten schrijft dat een mens
verplicht. Daarom:

- **Expliciet**, nooit als onderdeel van een run.
- **Idempotent per clausule**: twee keer inplannen levert geen twee uitnodigingen. Sleutel is
  `(audit_id, clausule_id, norm)`.
- **Append-only in de trail**: wie plande, voor welke clausule, met welke rol, en of het gelukt
  is. Dat spoor is zelf auditbewijs — het toont aan dat het gat is opgevolgd.
- **Achter de credential-beslissing.** Zie het voorstel: vandaag loopt dit via de `gws`-CLI en
  dus via een persoonlijke sessie.

## Wat een interview oplevert

De bestaande `interviews`-tabel: `(clausule_id, norm)` met bevinding, antwoord en notitie. Het
voorstel voegt daar niets aan toe — het vult de weg ernaartoe.

Belangrijk: het antwoord van de mens gaat **ongewijzigd** de tabel in. Geen samenvatting door een
model. Wat iemand in een audit heeft gezegd, is bewijs; een geparafraseerde versie is dat niet.
