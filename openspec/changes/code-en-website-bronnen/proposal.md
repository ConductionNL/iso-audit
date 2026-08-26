# Code-repositories en de website als auditbron

## Waarom

Het tool leest vandaag vijf bronnen: Drive, Planning, Jira, Nextcloud en Miro. Alle vijf zijn
**documentbronnen** — wat de organisatie over zichzelf heeft opgeschreven. Dat is precies de
zwakste soort bewijs, en de missie noemt dat ook zo: capability 1 is *onafhankelijke bronnen*,
en een beleidsdocument dat zegt dat er code-review plaatsvindt is geen bewijs dat er code-review
plaatsvindt.

Twee bronnen die dat wél zijn, staan nu buiten beeld:

**De repositories.** Voor ISO 27001 is de forge bijna de hardste bewijslast die er is. §8.25
(veilige ontwikkeling), §8.28 (veilig programmeren), §8.31 (scheiding ontwikkel/productie),
§8.32 (wijzigingsbeheer), §8.9 (configuratiebeheer) en §8.4 (toegang tot broncode) gaan
allemaal over dingen die in een repository zichtbaar zijn en nergens anders aantoonbaar. Het
vier-ogen-principe is geen belofte in een handboek maar een instelling op een branch, met een
geschiedenis van pull requests eronder.

Gemeten op de run van 2026-08-25: van de 47 bevestigde NC-kandidaten viel een blok van vier
onder het nieuwe thema *Ontwikkeling & wijzigingsbeheer* (§8.9, §8.25, §8.33). Alle vier zijn
geclassificeerd op basis van documenten die zeggen dat er iets zou moeten gebeuren. Geen enkele
is getoetst aan de plek waar het gebeurt.

**De website.** Wat een organisatie publiek beweert, is een verplichting die ze aangaat. Een
privacyverklaring, een securitypagina, een claim over certificering: dat zijn externe
toezeggingen die tegen de interne praktijk gelegd horen te worden (§5.31 wettelijke en
contractuele eisen, §5.34 privacy, en voor 9001 §8.2 eisen aan producten en diensten). Het gat
tussen wat je publiceert en wat je doet, is een klassieke NC die dit tool nu structureel mist —
niet omdat hij moeilijk te zien is, maar omdat de bron er niet is.

De code van de Conduction-website staat bovendien niet op GitHub maar op **Codeberg**. Eén
forge ondersteunen is daarom niet genoeg voor het eerste échte gebruik.

## Wat er verandert

- Een nieuwe source-adapter **`repo`** die repositories leest van GitHub én Codeberg.
- Een nieuwe source-adapter **`website`** die gepubliceerde pagina's leest.
- Beide configureerbaar in de UI én in een versiebeheerd YAML-bestand, met dezelfde
  wijzigingstrail als de bestaande bronconfiguratie.
- Beide read-only, met expliciete en gemeten limieten op wat er wordt opgehaald.

## Wat er niet verandert

- **Geen schrijfrichting.** Geen issues aanmaken, geen commits, geen PR's. Wie dat wil, bouwt
  een Sink; dat is een andere change met een eigen motivatie.
- **Geen volledige source-tree.** Een repository is geen documentmap. Wat er wordt gelezen is
  een expliciete, korte lijst bewijsdragende paden plus repository-metadata — zie de spec.
- **Geen crawler die een site uitkamt.** Sitemap of een opgegeven lijst URL's, en anders niets.

## Welke capability dit raakt

Capability 1, *onafhankelijke bronnen*, en die versterking is de hele reden. Capability 2
(patroondetectie) profiteert mee: een bewering in een document naast de praktijk in een
repository is precies het soort tegenstelling waar patroondetectie op zit te wachten.

Capability 3 (auditor-spiegel) wordt niet geraakt. Deze change levert bewijs aan; wie het weegt
verandert niet.
