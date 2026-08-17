"""Tests voor `ui.html` als contract met de API (taak 3 van change portal-dashboard).

Dit is geen browser-test. Wat hier bewaakt wordt, is het gat dat je in een
single-file UI zonder build-stap niet ziet: dat de UI een route aanroept die de API
niet meer heeft. De vorige UI ging uit van ongescopede paden (`/findings`); nu moet
elk audit-gescoped pad via de `A()`-helper lopen. Een vergeten `A()` levert in de
browser een 404 en hier een falende test.
"""

from __future__ import annotations

import re
from pathlib import Path

UI = Path("src/iso_audit/api/ui.html")

# Paden die bewust NIET onder een audit vallen.
ONGESCOPED = {
    "/audits",
    # Het documentenlandschap hoort bij de organisatie en niet bij één audit: één
    # voorraad die alle audits gebruiken. Daarom bewust zonder audit-prefix.
    "/landschap",
    "/instellingen/health",
    "/instellingen/options",
    "/instellingen/bronnen",
    "/instellingen/wijzigingen",
    "/instellingen/herkomst",
    "/instellingen/anthropic",
    "/me",
}


def _bron() -> str:
    return UI.read_text(encoding="utf-8")


def test_ui_is_een_bestand_zonder_buildstap() -> None:
    """Geen bundler, geen imports: de UI blijft te lezen en te patchen zonder toolchain."""
    bron = _bron()
    assert "<script>" in bron
    assert 'src="http' not in bron, (
        "externe scriptbron gevonden — dat is een buildstap in vermomming"
    )
    assert "import " not in bron.split("<script>")[1][:200]


def test_alle_auditcalls_lopen_via_de_prefix_helper() -> None:
    """Een vergeten `A()` is een 404 in de browser en verder onzichtbaar."""
    bron = _bron()
    losse = set()
    for m in re.finditer(r'(?:fetch|j)\(\s*(["`])(/[^"`]*)\1', bron):
        pad = m.group(2)
        basis = pad.split("?")[0]
        if not any(basis == o or basis.startswith(o + "/") for o in ONGESCOPED):
            losse.add(pad)
    assert not losse, f"deze paden missen de audit-prefix: {sorted(losse)}"


def test_prefix_helper_encodeert_het_audit_id() -> None:
    """Het id komt uit de URL-hash; zonder encoding breekt een id met vreemde tekens."""
    bron = _bron()
    assert "encodeURIComponent(AUDIT)" in bron


def test_drie_views_en_hash_routing() -> None:
    bron = _bron()
    for view in ("view-dashboard", "view-audit", "view-config"):
        assert f'id="{view}"' in bron
    assert 'window.addEventListener("hashchange"' in bron
    assert "#/audit/" in bron


def test_dashboard_toont_de_vier_gevraagde_kolommen() -> None:
    """Norm+periode met status, triage-voortgang, bronnen, en wie het laatst bewerkte."""
    bron = _bron()
    kop = bron.split("<th>Audit</th>")[1].split("</tr>")[0]
    for kolom in ("Status", "Triage", "Bronnen", "Laatst bewerkt"):
        assert f"<th>{kolom}</th>" in kop


def test_configscherm_kan_een_bron_koppelen() -> None:
    """Zapier-achtig: kies een bron, klik, configureer. Zonder cluster of beheerder."""
    bron = _bron()
    assert 'id="view-config"' in bron
    assert "toonBronForm" in bron and "bewaarBron" in bron
    assert "/instellingen/bronnen/" in bron


def test_openen_van_een_audit_laadt_ook_de_bronselectie() -> None:
    """Zonder deze aanroep is #config-form leeg tot iemand op een knop klikt, en stuurt
    `selectedConfig()` `sources: []` mee — een run die niets leest terwijl de auditor
    bronnen dénkt te hebben gekozen."""
    bron = _bron()
    lichaam = bron.split("async function openAudit(")[1].split("\nasync function")[0]
    assert "loadConfig()" in lichaam


def test_elk_configuratieveld_is_gewoon_invulbaar() -> None:
    """Geen `readonly`, geen extra bevestigingsstap.

    Er hebben hier achtereenvolgens een badge, een slot en een bevestigingsknop gestaan.
    De badge was te zwak (typen had geen effect), het slot te hard (een geroteerde key
    was niet te vervangen) en de knop overbodig zodra invullen écht werkt. Wat blijft is
    de projectregel uit `bron_config.py`: registratie is de controle, niet het moeilijk
    maken van configureren.
    """
    bron = _bron()
    invoer = bron.split("function toonBronForm(")[1].split("// Meteen zeggen")[0]
    assert "readonly" not in invoer.lower()
    assert "Toch overschrijven" not in invoer
    assert "Terug naar de omgeving" in invoer, "een overschrijving moet terug te draaien zijn"


def test_er_is_een_testknop_met_zichtbaar_resultaat() -> None:
    """Zonder terugkoppeling vul je een token in, krijg je "opgeslagen", en weet je nog
    steeds niet of de koppeling werkt."""
    bron = _bron()
    assert "async function testBron(" in bron
    assert "/instellingen/health/" in bron, "test één bron, niet alle bronnen"
    assert ">Testen</button>" in bron
    bewaar = bron.split("async function bewaarBron(")[1].split("\nasync function")[0]
    assert "testBron(naam)" in bewaar, "na opslaan meteen testen"


def test_een_mislukt_verzoek_laat_het_scherm_niet_op_laden_staan() -> None:
    """`j()` deed `(await fetch(url)).json()` zonder statuscontrole.

    Bij een 403 van de proxy — bijvoorbeeld na een cookie-rotatie, die alle sessies
    ongeldig maakt — klapt `.json()` om op de HTML-foutpagina, loopt de fout weg uit een
    niet-afgevangen `route()`, en blijft het scherm eeuwig op "laden…" staan. Weer een
    fout die zich voordoet als "er gebeurt niets".
    """
    bron = _bron()
    helper = bron.split("const j = async")[1].split("const esc")[0]
    assert "r.status === 401 || r.status === 403" in helper, "geen sessiecontrole"
    assert "if(!r.ok)" in helper, "andere foutcodes worden niet opgemerkt"
    assert "class SessieVerlopen" in bron

    # En de route vangt hem af met een leesbare melding in plaats van stilte.
    assert "async function veiligeRoute()" in bron
    veilig = bron.split("async function veiligeRoute()")[1].split("\nfunction uitloggen")[0]
    assert "Je sessie is verlopen" in veilig
    assert "Herlaad de pagina" in veilig
    assert 'addEventListener("hashchange", veiligeRoute)' in bron


def test_een_403_zonder_sessieprobleem_heet_niet_sessie_verlopen() -> None:
    """Een 403 hoeft niets met de sessie te maken te hebben.

    Gemeten op 2026-08-17: een globale nginx-regel op de ingress weigerde élk pad onder
    `/config/`, waarna dit scherm "Je sessie is verlopen" meldde terwijl de koptekst
    "ingelogd als …" toonde. Herladen hielp niet — er was niets mis met de sessie — en de
    melding stuurde naar het verkeerde probleem.

    Daarom toetst `j()` de sessie in plaats van hem te veronderstellen: bij een 401/403
    wordt `/me` opnieuw bevraagd. Blijft die 200, dan leeft de sessie en is het pad
    geweigerd.
    """
    bron = _bron()
    helper = bron.split("const j = async")[1].split("const esc")[0]
    assert 'await fetch("/me")' in helper, "de sessie wordt niet gemeten maar aangenomen"
    assert "if(!sessie.ok) throw new SessieVerlopen" in helper
    assert "throw new PadGeweigerd" in helper
    assert "class PadGeweigerd" in bron

    veilig = bron.split("async function veiligeRoute()")[1].split("\nfunction uitloggen")[0]
    assert "e instanceof PadGeweigerd" in veilig
    # De melding moet expliciet zeggen dat herladen niet helpt, anders blijft de auditor
    # het toch proberen — precies wat er op 17-08 gebeurde.
    assert "Herladen helpt hier niet" in veilig
    assert "ingelogd" in veilig


def test_lijstveld_rendert_rijen_en_vraagt_geen_kommas() -> None:
    """Meerdere Drive-locaties koppelen mag geen komma-getyp worden.

    `DriveSource` las al uit meerdere locaties — `_split_ids` splitst op komma's — maar het
    veld heette "Map-ID van de auditmap", enkelvoud, en niemand raadt dat daar een komma in
    mag. Het opslagformaat was naar de UI gelekt: één typefout maakte stil twee onbruikbare
    ID's van één goede.
    """
    bron = _bron()
    assert "function lijstVeld(" in bron
    assert "function lijstToevoegen(" in bron
    assert "function lijstVerwijderen(" in bron

    # De auditor krijgt een toevoegveld en rijen, geen scheidingsteken-instructie.
    veld = bron.split("function lijstVeld(")[1].split("\nfunction lijstRijen")[0]
    assert "plak een Drive-URL of ID" in veld
    assert "komma" not in veld.lower(), "de UI mag niet om een scheidingsteken vragen"

    # De komma bestaat alleen op de grens naar de server.
    bewaar = bron.split("async function bewaarBron(")[1].split("\nasync function")[0]
    assert 'join(",")' in bewaar


def test_de_rijen_tonen_de_naam_niet_alleen_het_id() -> None:
    """Een ID van 44 tekens zegt een mens niets.

    De spec eist "de naam zoals Drive die kent" per locatie. De statusregels deden dat al;
    de bewerkbare rijen toonden nog het kale ID, en dan moet je uit je hoofd weten dat
    `0AAP…` de ISO-drive is. Het ID blijft er wel bij staan: je verwijdert een rij op basis
    van wat er staat, en twee mappen kunnen dezelfde naam hebben.
    """
    bron = _bron()
    assert "const _locatieNamen" in bron
    assert "function onthoudLocatieNamen(" in bron
    # De namen komen uit dezelfde healthcheck als de statusregels, zodat ze niet uiteen
    # kunnen lopen met wat daar gemeld wordt.
    regels = bron.split("function locatieRegels(")[1].split("\nasync function testBron")[0]
    assert "onthoudLocatieNamen(locaties)" in regels

    rijen = bron.split("function lijstRijen(")[1].split("\n// Hetzelfde herleiden")[0]
    assert "_locatieNamen[w]" in rijen, "de rij kijkt de naam niet op"
    assert "bekend.naam" in rijen
    assert "mini mono" in rijen, "het ID moet zichtbaar blijven onder de naam"


def test_dezelfde_locatie_kan_niet_twee_keer() -> None:
    """Een geplakte URL van een locatie die al als kaal ID staat, is dezelfde locatie."""
    bron = _bron()
    toevoegen = bron.split("function lijstToevoegen(")[1].split("\nfunction lijstVerwijderen")[0]
    assert "idUitUrl(" in toevoegen, "zonder normalisatie herkent de dubbelcheck de URL niet"
    assert "staat er al" in toevoegen


def test_status_per_locatie_zichtbaar_zonder_te_testen() -> None:
    """Een groene bron met één lege locatie moet dat op de kaart zelf laten zien.

    Anders is de samenvatting precies de dekkingsclaim die niet klopt: de auditor ziet
    groen en concludeert dat de scope gedekt is.
    """
    bron = _bron()
    assert "function locatieRegels(" in bron
    regels = bron.split("function locatieRegels(")[1].split("\nasync function testBron")[0]
    # Het getal is niet-recursief; dat moet erbij staan, anders leest het als een totaal.
    assert "direct in deze locatie" in regels
    assert "l.reden" in regels, "een waarschuwing zonder reden helpt niemand"
    # En de kaart rendert ze, niet alleen de testknop.
    assert bron.count("locatieRegels(") >= 3


def test_de_ui_wordt_niet_gecachet(tmp_path: Path) -> None:
    """Eén HTML-bestand zonder buildstap heeft geen versie in de URL. Zonder `no-store`
    zit een auditor na een uitrol op een oud scherm zonder het te merken — dat kostte hier
    een sessie aan verwarring over knoppen die er wél waren."""
    from fastapi.testclient import TestClient

    from iso_audit.api.app import create_app
    from iso_audit.api.registry import AuditRegistry

    from .conftest import AUDITOR, EXAMPLES, NORMS

    registry = AuditRegistry(tmp_path / "audits")
    registry.root.mkdir(parents=True)
    app = create_app(registry, profile=str(EXAMPLES / "conduction.profile.yaml"), norms_dir=NORMS)
    r = TestClient(app, headers={"X-Forwarded-Email": AUDITOR}).get("/")

    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")


def test_de_ui_kent_alle_herkomsten_die_de_server_kan_geven() -> None:
    """Een single-file UI heeft geen buildstap; dit is de enige manier om te merken dat de
    backend een herkomst toevoegt die het scherm niet kan tonen."""
    from iso_audit.config.settings import Bron

    bron = _bron()
    labels = bron.split("const BRON_LABEL")[1].split("};")[0]
    for waarde in Bron.__args__:  # type: ignore[attr-defined]
        assert waarde in labels, f"herkomst {waarde!r} heeft geen label in de UI"


def test_geheime_velden_worden_als_wachtwoord_getoond() -> None:
    bron = _bron()
    assert 'type="${v.geheim ? "password" : "text"}"' in bron


def test_configscherm_noemt_geen_env_vars_of_secrets() -> None:
    """De auditor hoeft niets te weten van env-vars, Secrets of een cluster."""
    bron = _bron()
    blok = bron.split('id="view-config"')[1].split("</section>")[0]
    for jargon in ("env-var", "Secret", "cluster", "manifest", "JIRA_", "MIRO_"):
        assert jargon not in blok, f"implementatiejargon in het configscherm: {jargon}"


def test_audit_wissel_maakt_de_vorige_audit_leeg() -> None:
    """Anders zie je data van audit A terwijl de kop audit B zegt."""
    bron = _bron()
    blok = bron.split("async function openAudit()")[1].split("async function loadRuns()")[0]
    assert "triage-wrap" in blok and 'innerHTML = ""' in blok


def test_gelijktijdigheidswaarschuwing_wordt_getoond() -> None:
    """De registry levert `andere_actief`; de UI moet er iets mee doen."""
    bron = _bron()
    assert "andere_actief" in bron
    assert "audit-warn" in bron


def test_uitlogknop_bestaat() -> None:
    """Een portaal zonder uitlogknop kun je alleen verlaten door je browser te sluiten."""
    bron = _bron()
    assert 'id="uitloggen"' in bron
    assert "/oauth2/sign_out" in bron
    assert 'j("/me")' in bron


def test_normkeuze_is_een_enum_zonder_jargon() -> None:
    """De auditor kiest een norm of beide; slugs, id-formaat en YAML horen niet in de UI."""
    bron = _bron()
    formulier = bron.split('id="nieuw-audit"')[1].split("</div>")[0]
    assert "select" in formulier and "na-norm" in formulier
    assert "checkbox" not in formulier, "vinkjes: je kiest een auditscope, geen verzameling"
    for jargon in ("YAML", "yaml", "norm-DB", "9001_27001", "JJJJ-Qn"):
        assert jargon not in formulier, f"implementatiejargon in het formulier: {jargon}"


def test_normlabel_verbergt_de_slug() -> None:
    bron = _bron()
    assert "function normLabel" in bron
    assert "ISO ${m[1]}" in bron


def test_configscherm_toont_de_herkomst_per_veld() -> None:
    """Zonder herkomst-badge typt een auditor iets in dat stil geen effect heeft."""
    bron = _bron()
    assert 'j("/instellingen/herkomst")' in bron
    assert "bronBadge" in bron
    assert "BRON_LABEL" in bron


def test_door_beheerder_gezette_velden_zijn_zichtbaar_vast() -> None:
    """env en yaml kunnen in de UI niet overschreven worden; dat moet je kunnen zien."""
    bron = _bron()
    assert 'h.bron === "env" || h.bron === "yaml"' in bron
    assert "bronbadge.vast" in bron
