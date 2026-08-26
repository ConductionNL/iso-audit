# Ontwerp — code-repositories en website als bron

## Eén `repo`-adapter of twee (GitHub en Codeberg apart)?

De huisregel in dit project is expliciete herhaling boven abstractie: drie identieke registries
met een `@register`-decorator, niet één meta-class. Die regel zou hier twee adapters voorschrijven.

**Toch wordt het er één, en dat is een bewuste afwijking.** De reden is waar de herhaling zou
landen. Wat verschilt tussen GitHub en Codeberg is de HTTP-aanroep: andere host, ander
auth-schema, andere JSON-veldnamen. Wat *niet* verschilt is de auditinhoud — welke paden bewijs
dragen, welke repository-instellingen §8.4 en §8.32 raken, hoe een branch-protectie zich
verhoudt tot het vier-ogen-principe. Die logica twee keer neerzetten betekent dat ze uit elkaar
gaat lopen, en dan levert het tool voor de ene forge ander bewijs dan voor de andere zonder dat
iemand dat merkt. Dat is een ernstiger auditrisico dan een tweede API-client.

Dus: één adapter `repo`, met twee dunne clients (`_github.py`, `_codeberg.py`) die allebei
dezelfde `Repositoriegegevens` teruggeven. De grens is scherp: een client doet HTTP en
veldvertaling, en **niets** wat met de norm te maken heeft.

Codeberg draait Forgejo, dat een Gitea-compatibele API heeft. De twee clients zijn daarmee
vergelijkbaar van omvang.

## Wat lezen we uit een repository?

Niet de source-tree. Een repository is geen documentmap, en 700 bestanden inlezen levert ruis en
een run van uren. Wat wordt gelezen is een korte, **expliciete** lijst — geen glob-magie, geen
"alles onder docs/":

| Wat | Waarvoor |
|---|---|
| `README`, `SECURITY.md`, `CONTRIBUTING.md`, `CODEOWNERS`, `LICENSE` | §5.2 rollen, §8.28, 9001 §7.5 |
| `.github/workflows/*`, `.forgejo/workflows/*`, `.gitlab-ci.yml` | §8.25, §8.31 geautomatiseerde poorten |
| `.pre-commit-config.yaml`, linter-configuratie | §8.28 veilig programmeren |
| `dependabot.yml` / `renovate.json` | §8.8 technische kwetsbaarheden |
| Repository-metadata: zichtbaarheid, branch-protectie, review-eis, archiefstatus | §8.4, §8.32 |
| Aggregaten over de laatste N pull requests: aantal, aandeel met review, aandeel zelf-gemerged | §8.32, vier-ogen |

Die laatste rij is het interessantst en het gevoeligst. **Aggregaten, geen personen.** Het tool
telt hoeveel wijzigingen zonder tweede paar ogen zijn gemerged; het noemt niet wie dat deed. Een
NC gaat over een proces dat niet werkt, niet over een collega. Dezelfde regel staat al in de
review-prompt: *wie* is een rol en nooit een persoon.

## Welke repositories?

Van Codeberg hoort er **één** in scope: `conduction/conduction-website`, de code achter de site.
De overige 62 zijn spiegels van GitHub; die twee keer auditen levert twee keer hetzelfde bewijs
en een dekkingscijfer dat nergens op slaat.

Dat is organisatiekennis en geen API-feit: van de 50 opgevraagde Codeberg-repo's staat er op
2026-08-26 **geen enkele** als `mirror` gemarkeerd. Het tool kan het dus niet afleiden, en dat is
precies waarom de configuratie een expliciete lijst is en geen "alles van de organisatie".

Van GitHub gaat het om een selectie uit 183 actieve repo's — welke, is een auditkeuze die de
auditor maakt en niet een die uit een teller volgt.

## Wat lezen we van een website?

Sitemap eerst (`/sitemap.xml`), en anders de opgegeven URL-lijst. Geen crawler die links volgt:
dat is niet te begrenzen, niet te herhalen en niet uit te leggen aan wie vraagt wat het tool
heeft gezien. `robots.txt` wordt gerespecteerd — het tool leest een site die het niet bezit.

Per pagina wordt de zichtbare tekst opgeslagen, geen HTML. Dezelfde behandeling als een ODF- of
PDF-document, en dezelfde limieten.

## Waar staat de configuratie?

De eis is *configureerbaar in de UI én YAML in de repo*, en die twee kunnen makkelijk uit elkaar
gaan lopen. Eén waarheid:

- **De live configuratie is één YAML-bestand op het datavolume**, `bronnen.yaml`, naast de
  bestaande `bron_config.json`. Dat bestand is wat de run leest.
- **De UI bewerkt datzelfde bestand** via de API, en elke wijziging gaat in dezelfde
  append-only trail als de huidige bronconfiguratie (`bron_config_log.jsonl`).
- **De repo levert `examples/bronnen.yaml`** als sjabloon met commentaar. Dat is de
  versiebeheerde vorm: het formaat, de velden en een werkend voorbeeld. Het is nadrukkelijk
  géén tweede live-configuratie.
- Het live-bestand is gewoon tekst en kan gecommit worden wie dat wil — maar het tool leest
  nooit uit de repo-checkout. Anders is er weer geen weten welke van de twee gold.

Geheimen staan er niet in. Tokens gaan via `config/settings.py` (`VELDEN`, `geheim=True`), net
als het Jira- en Nextcloud-wachtwoord, en komen uit het cluster-secret.

## Limieten, expliciet en gemeten

Elke bron die van buiten komt heeft een plafond nodig, en het plafond hoort instelbaar te zijn —
dezelfde les als bij `MAX_ODF_INHOUD` en `MAX_ANTWOORD_TOKENS`, waar een hardgecodeerde grens
eerst onzichtbaar knelde en daarna niet te testen was.

- Maximum aantal repositories, maximum aantal pagina's per site.
- Maximum bestandsgrootte per opgehaald bestand.
- Maximum aantal pull requests waarover geaggregeerd wordt.
- Een verzoekvertraging tegen een externe host.

Overschrijding is een **melding**, geen stille afkapping. De stille afkapping is de fout die dit
project het vaakst heeft gemaakt: MIME-types die zonder melding werden overgeslagen, een
review-antwoord dat werd afgekapt en "onleesbaar" heette, 18 ISO 9001-clausules die nooit werden
getoetst. Wat niet gelezen is, moet in de dekking staan.

## Wat we niet doen en waarom

- **Geen git clone.** Een checkout betekent willekeurige bestanden op de schijf van een pod met
  `readOnlyRootFilesystem`, en betekent code van buiten binnenhalen. De API's leveren wat we
  nodig hebben.
- **Geen secret-scanning.** Verleidelijk, maar het betekent dat het tool geheimen leest en
  vastlegt. Wie dat wil gebruikt gitleaks in de repo zelf; dat is dan een bevinding met een
  verwijzing, niet met de inhoud.
- **Geen privérepositories van individuen.** Alleen wat onder de organisatie valt en in de
  configuratie is opgegeven.
