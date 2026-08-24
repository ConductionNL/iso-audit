"""`JiraSource` — Jira Cloud REST API v3 adapter (§3.4.1-3).

Read-only: enumereert Jira issues als `Document`s en kan ze ook als
`Finding`s exposeren (voor backlog-items die direct compliance-bewijs
zijn — bv. een ISO-aanbevelings-ticket).

Auth: persoonlijke Atlassian API-token via env-vars (`JIRA_BASE_URL`,
`JIRA_USER_EMAIL` — `JIRA_EMAIL` als fallback —, `JIRA_API_TOKEN`) met HTTP
basic auth (Atlassian's standaard voor Cloud-token-auth). JQL-config via
`JIRA_JQL` (leeg = geen filter). Scope op project(en) via `JIRA_PROJECTS`
(komma-gescheiden, bv. "ISO"): wordt als `project in (…)` AND-prefix op elke
query gezet zodat een run binnen de ISO-scope blijft.

Pagination: via Jira Cloud's enhanced search `/rest/api/3/search/jql`
(de oude `/search` is verwijderd, HTTP 410). Token-gebaseerd: paginate via
`nextPageToken` tot `isLast`.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import Any

import requests

from iso_audit.config.verbinding import normaliseer
from iso_audit.sources import register
from iso_audit.sources.base import Document, Finding

logger = logging.getLogger(__name__)

_DEFAULT_PAGE_SIZE = 100
_DEFAULT_TIMEOUT_S = 30.0

_OPENSTAAND = "statusCategory != Done"
"""Welke issues openstaande punten zijn: alles wat nog niet afgerond is, binnen de
geconfigureerde projectscope (`JIRA_PROJECTS`).

Hier stond eerder `labels in (iso27001, iso9001, compliance) AND statusCategory != Done`.
Gemeten in een echte tenant: die labels bestonden daar niet — gebruikt werden onder meer
`interne_audit`, `managementreview2026`, `ISO_algemeen`, `externeaudit`. De filter leverde
dus stil nul punten op, terwijl er 25 open issues in het ISO-project stonden.

Een project is bovendien de robuustere scope: labels zijn per organisatie verschillend en
veranderen, een projectsleutel is een afspraak. Wie tóch op labels wil filteren zet
`JIRA_FINDINGS_JQL`."""

_ONBEGRENSD_VANGNET = "updated >= -365d"
"""Begrenzing als er noch `JIRA_PROJECTS` noch `JIRA_JQL` is ingesteld.

Jira Cloud antwoordt op een lege query met HTTP 400 ("Unbounded JQL queries are not
allowed here"). Een jaar terugkijken is voor een auditperiode een verdedigbare ondergrens
en het is zichtbaar in de logregel; stil niets lezen is dat niet. Wie een andere scope wil,
zet `JIRA_PROJECTS` of `JIRA_JQL`."""


@register
class JiraSource:
    """Source-adapter voor Jira Cloud issues."""

    naam: str = "jira"

    levert_opvolgpunten: bool = True
    """Jira levert **openstaande punten**, geen bewijsmateriaal.

    Een ticket met label `iso27001` is een afgesproken verbeteractie die nog loopt. Het
    tegen elke clausule classificeren leverde bevindingen als "dit ticket bewijst §4.1
    niet" — ruis, plus LLM-kosten per ticket. Zie `sources/opvolgpunten.py`."""

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        default_jql: str | None = None,
        page_size: int = _DEFAULT_PAGE_SIZE,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        """Construct met expliciete creds of fallback naar env-vars."""
        self._base_url = (base_url or os.environ.get("JIRA_BASE_URL", "")).rstrip("/")
        # JIRA_USER_EMAIL is de gekozen naam; JIRA_EMAIL blijft als fallback voor
        # bestaande configs (boring & auditable: geen stille breaking change).
        self._email = email or os.environ.get("JIRA_USER_EMAIL") or os.environ.get("JIRA_EMAIL", "")
        self._api_token = api_token or os.environ.get("JIRA_API_TOKEN", "")
        self._jql = default_jql or os.environ.get("JIRA_JQL", "")
        # Scope-filter op project(en) — immutable runtime-conf. Komma-gescheiden,
        # bv. JIRA_PROJECTS="ISO" of "ISO,COMP". Wordt als AND-prefix op elke
        # effectieve JQL gezet (documenten én findings).
        self._projects = [
            p.strip() for p in os.environ.get("JIRA_PROJECTS", "").split(",") if p.strip()
        ]
        self._page_size = page_size
        self._timeout_s = timeout_s
        self._api_basis: str | None = None

    @property
    def scoped(self) -> bool:
        """Is dit een scoped service-token (`ATSTT…`) in plaats van een gebruikerstoken?

        Atlassian kent twee soorten. Een **gebruikers**-token (`ATATT…`) hoort bij een
        persoon en gaat via Basic auth met diens e-mailadres als gebruikersnaam. Een
        **service**-token hoort bij een service-account, gaat via `Authorization: Bearer`
        en heeft géén e-mailadres nodig — dat laatste is precies wat je wil als de
        koppeling niet aan een persoon mag hangen.

        Onderscheid op prefix en niet op configuratie: dan hoeft niemand een extra keuze
        te maken die de credential zelf al weggeeft, en kan hij ook niet fout staan.
        """
        return self._api_token.startswith("ATSTT")

    def _basis(self) -> str:
        """Het URL-voorvoegsel voor API-calls.

        Een scoped token werkt **niet** op de site-URL; die geeft 403 op elk endpoint,
        ook op `serverInfo`. Hij moet naar de gateway `api.atlassian.com/ex/jira/{cloudId}`.
        De cloud-ID is zonder authenticatie op te halen via `/_edge/tenant_info`, dus dat
        hoeft niemand te configureren; het antwoord wordt per instantie onthouden.
        """
        if not self.scoped:
            return self._base_url
        if self._api_basis is None:
            resp = requests.get(
                f"{self._base_url}/_edge/tenant_info",
                headers={"Accept": "application/json"},
                timeout=self._timeout_s,
            )
            if not resp.ok:
                raise OSError(f"Cloud-ID opvragen mislukte: HTTP {resp.status_code}")
            cloud_id = str(resp.json().get("cloudId") or "")
            if not cloud_id:
                raise OSError("Geen cloudId in het antwoord van tenant_info")
            self._api_basis = f"https://api.atlassian.com/ex/jira/{cloud_id}"
        return self._api_basis

    def _scope_jql(self, base_jql: str) -> str:
        """Beperk een JQL tot de geconfigureerde projecten (`JIRA_PROJECTS`).

        Geen projecten geconfigureerd → JQL blijft ongewijzigd. Anders wordt
        `project in ("ISO", …)` als AND-conditie voorgevoegd, zodat een run
        binnen de ISO-scope blijft, ongeacht de onderliggende query.
        """
        if not self._projects:
            # Jira Cloud weigert een onbegrensde query: HTTP 400 "Unbounded JQL queries
            # are not allowed here". Zonder projectscope en zonder eigen JQL stuurde deze
            # adapter een lege string, en dan leverde een gekozen Jira-bron stil nul
            # documenten. Een tijdvenster is de minst verrassende begrenzing: het beperkt
            # wat je leest, niet wélke projecten je ziet.
            return base_jql if base_jql.strip() else _ONBEGRENSD_VANGNET
        quoted = ", ".join(f'"{p}"' for p in self._projects)
        scope = f"project in ({quoted})"
        return f"({scope}) AND ({base_jql})" if base_jql.strip() else scope

    def list_documents(self, filter: dict[str, object] | None = None) -> Iterator[Document]:
        """Iterate over Jira issues; elke issue wordt een `Document`.

        `filter` mag een `{"jql": "..."}`-veld bevatten om de default JQL te
        overschrijven. Andere keys worden genegeerd (read-only contract).
        """
        jql = ""
        if filter and isinstance(filter.get("jql"), str):
            jql = str(filter["jql"])
        elif self._jql:
            jql = self._jql

        for issue in self._iterate_issues(self._scope_jql(jql)):
            yield _issue_to_document(issue)

    def fetch_content(self, doc: Document) -> str:
        """Haal de volledige tekstuele inhoud van één issue op.

        Jira's `description` is in Atlassian Document Format (ADF). Voor MVP
        retourneren we een platte-tekst-rendering van `description` + de
        comments. Rich-content rendering komt mee met §3.4.6 docs of bij
        eerste integer-run als het nodig blijkt.
        """
        url = f"{self._basis()}/rest/api/3/issue/{doc.id}"
        resp = self._http_get(url, params={"fields": "description,comment"})
        data = resp.json()
        return _render_issue_inhoud(data)

    def list_findings(self, sessie_id: str) -> Iterator[Finding]:
        """Issues met een ISO-label of `compliance`-label worden als Finding gemodelleerd.

        `sessie_id` correspondeert aan de audit-run; we voegen het toe als
        prefix aan finding.id zodat dezelfde issue in verschillende runs
        verschillende Finding-id's krijgt.

        Filter via JQL: `labels in (iso27001, iso9001, compliance) AND
        statusCategory != Done`. Override mogelijk via env-var
        `JIRA_FINDINGS_JQL`.
        """
        findings_jql = os.environ.get("JIRA_FINDINGS_JQL", _OPENSTAAND)
        for issue in self._iterate_issues(self._scope_jql(findings_jql)):
            yield _issue_to_finding(issue, sessie_id)

    def healthcheck(self) -> dict[str, object]:
        """Status + tenant (`base_url`) en config-staat.

        `/rest/api/3/myself` is Atlassian's "wie ben ik"-endpoint: de lichtste read-only
        call die bewijst dat de credential geldig is. `user` erbij is geen sier — die laat
        zien op wélk account het token staat, en dat is precies de vraag bij het
        loskoppelen van persoonsgebonden credentials.
        """
        # Bij een scoped service-token is een e-mailadres niet nodig: dat is alleen de
        # gebruikersnaam voor Basic auth met een persoonlijk token. Het als verplicht
        # opvoeren zou vragen om een persoonsgebonden gegeven dat de koppeling juist niet
        # mag hebben.
        vereist = [("het Jira-adres", self._base_url), ("het API-token", self._api_token)]
        if not self.scoped:
            vereist.insert(1, ("de service-account e-mail", self._email))
        ontbreekt = [label for label, waarde in vereist if not waarde]
        if ontbreekt:
            # Eigen tekst, geen leveranciersrespons — die mag dus letterlijk door. Wel in
            # auditor-taal: het configuratiescherm is niet de plek om env-var-namen te leren.
            return {
                "status": "fail",
                "naam": self.naam,
                "soort": "niet_geconfigureerd",
                "reden": f"Nog niet ingevuld: {', '.join(ontbreekt)}.",
            }
        try:
            resp = self._http_get(f"{self._basis()}/rest/api/3/myself")
            user = resp.json()
            return {
                "status": "ok",
                "naam": self.naam,
                "tenant": self._base_url,
                "user": user.get("displayName", ""),
            }
        except Exception as e:
            # `_http_get` bouwt zijn fout als "Jira API {code} op {url}: {resp.text}" — dus
            # tenant-URL plus responsbody. Die tekst hoort in het serverlog, niet in de
            # browser en niet in een 400 van `/run/start`.
            soort, tekst = normaliseer(e, bron=self.naam)
            return {
                "status": "fail",
                "naam": self.naam,
                "soort": soort,
                "reden": tekst,
            }

    def _iterate_issues(self, jql: str) -> Iterator[dict[str, Any]]:
        """Paginated iterator over Jira's enhanced search-API (`/search/jql`).

        De oude `/rest/api/3/search` is door Atlassian verwijderd (HTTP 410).
        De enhanced search pagineert via een opaque `nextPageToken` i.p.v.
        `startAt` en geeft geen `total` meer terug; we stoppen bij `isLast`,
        een ontbrekende token of een lege pagina.
        """
        if not self._base_url:
            return
        url = f"{self._basis()}/rest/api/3/search/jql"
        next_token: str | None = None
        while True:
            params: dict[str, object] = {
                "jql": jql,
                "maxResults": self._page_size,
                "fields": "summary,status,labels,updated,description",
            }
            if next_token:
                params["nextPageToken"] = next_token
            resp = self._http_get(url, params=params)
            data = resp.json()
            issues: list[dict[str, Any]] = data.get("issues", [])
            yield from issues
            next_token = data.get("nextPageToken")
            if data.get("isLast") or not next_token or not issues:
                break

    def _http_get(self, url: str, params: dict[str, object] | None = None) -> requests.Response:
        kop: dict[str, str] = {"Accept": "application/json"}
        auth: tuple[str, str] | None = None
        if self.scoped:
            kop["Authorization"] = f"Bearer {self._api_token}"
        else:
            auth = (self._email, self._api_token)
        # requests accepts a mapping; cast for mypy precision.
        resp = requests.get(
            url,
            params=params or {},  # type: ignore[arg-type]
            auth=auth,
            headers=kop,
            timeout=self._timeout_s,
        )
        if not resp.ok:
            raise OSError(f"Jira API {resp.status_code} op {url}: {resp.text[:200]}")
        return resp


def _issue_to_document(issue: dict[str, Any]) -> Document:
    """Map Jira-issue-JSON naar `Document`."""
    fields = issue.get("fields", {})
    return Document(
        id=str(issue.get("key", "")),
        titel=str(fields.get("summary", "")),
        bron="jira",
        type="issue",
        laatst_gewijzigd=str(fields.get("updated", "")),
        inhoud_uri=f"jira://{issue.get('key', '')}",
    )


def _issue_to_finding(issue: dict[str, Any], sessie_id: str) -> Finding:
    """Map Jira-issue naar `Finding`. Labels worden clausule-id's.

    Het id is de **Jira-sleutel**, niet `f"{sessie_id}:{key}"`. Dat sessie-id verschilt per run,
    dus dezelfde issue kreeg elke run een nieuw id en werd als nieuw opvolgpunt opgeslagen.
    Gemeten op 2026-08-24 met drie runs op één database: 83 unieke sleutels stonden er na twee
    runs 166 keer in, zonder ook maar één modelaanroep — het waren letterlijk dezelfde punten.

    Opvolgpunten staan buiten de triage, dus de werkset bleef schoon. Wat scheefliep is elke
    telling van "hoeveel opvolging is er", en dat is precies waar deze rijen voor bestaan.

    `sessie_id` blijft in de signatuur: de aanroeper geeft hem mee en hij hoort bij de context
    van het ophalen, niet bij de identiteit van de issue.
    """
    fields = issue.get("fields", {})
    labels: list[str] = list(fields.get("labels", []) or [])
    clausule_ids = [_label_naar_clausule(label) for label in labels]
    clausule_ids = [c for c in clausule_ids if c]
    return Finding(
        id=str(issue.get("key", "")),
        bron="jira",
        clausule_ids=clausule_ids,
        omschrijving=str(fields.get("summary", "")),
        bewijs_uris=[f"jira://{issue.get('key', '')}"],
    )


def _label_naar_clausule(label: str) -> str:
    """Heuristische map van Jira-label naar clausule-id.

    Voor MVP geven we 'iso27001' / 'iso9001' / 'compliance' direct terug;
    een fijnere map (e.g. `iso27001-5.11` → `5.11`) kan in een
    pipeline-extension worden toegevoegd.
    """
    prefix = "iso27001-"
    if label.startswith(prefix):
        return label[len(prefix) :]
    prefix2 = "iso9001-"
    if label.startswith(prefix2):
        return label[len(prefix2) :]
    return ""


def _render_issue_inhoud(data: dict[str, Any]) -> str:
    """Maak een platte-tekst-rendering van een Jira issue."""
    fields = data.get("fields", {})
    parts: list[str] = []
    desc = fields.get("description")
    if isinstance(desc, dict):
        parts.append(_render_adf(desc))
    elif isinstance(desc, str):
        parts.append(desc)
    comments = (
        fields.get("comment", {}).get("comments", [])
        if isinstance(fields.get("comment"), dict)
        else []
    )
    for comment in comments:
        body = comment.get("body")
        if isinstance(body, dict):
            parts.append("\n---\n" + _render_adf(body))
        elif isinstance(body, str):
            parts.append("\n---\n" + body)
    return "\n".join(parts).strip()


def _render_adf(node: dict[str, Any]) -> str:
    """Minimale Atlassian Document Format → plain text."""
    parts: list[str] = []
    text = node.get("text")
    if isinstance(text, str):
        parts.append(text)
    for child in node.get("content", []) or []:
        if isinstance(child, dict):
            parts.append(_render_adf(child))
    if node.get("type") == "paragraph":
        parts.append("\n")
    return "".join(parts)
