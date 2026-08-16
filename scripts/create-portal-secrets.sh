#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: installer
#
# scripts/create-portal-secrets.sh — maak de out-of-band Secrets voor het
# iso-audit-portaal aan in namespace iso-platform.
#
# Waarom een script en geen instructielijst: de kubectl-regels zijn lang, de
# key-namen moeten exact matchen met deployment.yaml, en een typfout levert een
# pod die start maar niet werkt. Dit script leest de waarden uit de omgeving,
# controleert wat verplicht is, en is idempotent (--dry-run + apply, dus opnieuw
# draaien overschrijft in plaats van te falen).
#
# De waarden komen NOOIT als argument op de commandline (die staat in je
# shell-history en in de procestabel) maar uit env-vars, of uit een env-bestand in de
# repo-root. Dat bestand wordt geparsed en NIET ge-`source`d: een regel als
# `X=$(...)` zou anders worden uitgevoerd, en zo'n bestand komt van buiten dit script.
# Alleen de sleutels die hieronder in `lees_env_bestand` staan worden overgenomen; een
# expliciet gezette omgevingsvariabele gaat altijd vóór.
#
# Writes: Secrets iso-audit-portal-{oauth,llm,sources,google} in iso-platform
# Idempotent: ja — apply van een gegenereerd manifest
# Requires: kubectl met toegang tot het cluster, openssl
# Style-afwijking: geen
#
# Usage:
#   # eenvoudigst — waarden komen uit het env-bestand in de repo-root:
#   ./scripts/create-portal-secrets.sh
#
#   # een ander bestand, of juist geen:
#   ./scripts/create-portal-secrets.sh --env-file ~/geheim/portaal.env
#   ./scripts/create-portal-secrets.sh --geen-env-file
#
#   # minimaal — alleen oauth2-proxy (verplicht om de pod te laten starten):
#   KEYCLOAK_CLIENT_SECRET='...' ./scripts/create-portal-secrets.sh
#
#   # oauth-Secret staat er al: laat KEYCLOAK_CLIENT_SECRET weg, hij blijft ongemoeid
#   ANTHROPIC_KEY='sk-ant-...' JIRA_API_TOKEN='ATSTT...' \
#     GOOGLE_SA_FILE=/pad/naar/service-account.json \
#     ./scripts/create-portal-secrets.sh
#
#   # met de LLM-key erbij (org-workspace-key, geen persoonlijke token):
#   KEYCLOAK_CLIENT_SECRET='...' ANTHROPIC_KEY='sk-ant-...' \
#     ./scripts/create-portal-secrets.sh
#
#   # volledig, inclusief bronnen en het Google-service-account:
#   KEYCLOAK_CLIENT_SECRET='...' ANTHROPIC_KEY='sk-ant-...' \
#     JIRA_BASE_URL='https://x.atlassian.net' JIRA_USER_EMAIL='iso@conduction.nl' \
#     JIRA_API_TOKEN='...' MIRO_API_TOKEN='...' \
#     GOOGLE_SA_FILE=/pad/naar/service-account.json \
#     ./scripts/create-portal-secrets.sh

set -euo pipefail

readonly NAMESPACE="iso-platform"

SKIP_OAUTH=false
ENV_FILE=".env"

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --env-file)
      ENV_FILE="${2:?--env-file vraagt een pad}"
      shift
      ;;
    --geen-env-file) ENV_FILE="" ;;
    -h | --help)
      sed -n '/^# Usage:/,/^$/p' "$0" >&2
      exit 0
      ;;
    *)
      err "onbekend argument: $1"
      exit 2
      ;;
    esac
    shift
  done
}

err() {
  echo "error: $*" >&2
}

# Maak of vervang een Secret zonder de waarden in de shell-history te zetten.
apply_secret() {
  local naam="$1"
  shift
  kubectl create secret generic "$naam" \
    --namespace "$NAMESPACE" \
    "$@" \
    --dry-run=client -o yaml | kubectl apply -f -
}

# Vul ontbrekende waarden aan uit een .env-bestand.
#
# Bewust géén `source`: een .env met `$(...)` erin zou dan uitgevoerd worden, en zo'n
# bestand komt van buiten dit script. Dit leest alleen regels van de vorm SLEUTEL=waarde
# en pakt uitsluitend de sleutels die hieronder staan.
#
# Wat al in de omgeving staat wint: zo kun je één waarde overrulen zonder het bestand
# aan te passen. Dezelfde volgorde als de app zelf aanhoudt.
#
# De app en dit script gebruiken niet overal dezelfde naam — de app leest
# `ANTHROPIC_API_KEY` en `GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE`, dit script kent ze als
# `ANTHROPIC_KEY` en `GOOGLE_SA_FILE`. Beide vormen worden herkend.
lees_env_bestand() {
  local pad="$1"
  [[ -f "$pad" ]] || return 0
  echo "  waarden aanvullen uit ${pad} (bestaande omgevingsvariabelen blijven voorgaan)"

  local regel sleutel waarde doel
  while IFS= read -r regel || [[ -n "$regel" ]]; do
    regel="${regel%$'\r'}"
    [[ "$regel" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$regel" == *=* ]] || continue

    sleutel="${regel%%=*}"
    waarde="${regel#*=}"
    sleutel="${sleutel#export }"
    # witruimte rond de sleutel weg
    sleutel="${sleutel//[[:space:]]/}"
    # omringende aanhalingstekens weg, indien aanwezig
    if [[ "$waarde" == \"*\" || "$waarde" == \'*\' ]]; then
      waarde="${waarde:1:${#waarde}-2}"
    fi
    [[ -n "$waarde" ]] || continue

    case "$sleutel" in
    KEYCLOAK_CLIENT_SECRET) doel="KEYCLOAK_CLIENT_SECRET" ;;
    ANTHROPIC_KEY | ANTHROPIC_API_KEY) doel="ANTHROPIC_KEY" ;;
    JIRA_BASE_URL) doel="JIRA_BASE_URL" ;;
    JIRA_USER_EMAIL) doel="JIRA_USER_EMAIL" ;;
    JIRA_API_TOKEN) doel="JIRA_API_TOKEN" ;;
    MIRO_API_TOKEN) doel="MIRO_API_TOKEN" ;;
    GOOGLE_SA_FILE | GOOGLE_WORKSPACE_CLI_CREDENTIALS_FILE) doel="GOOGLE_SA_FILE" ;;
    *) continue ;;
    esac

    # Alleen invullen wat nog leeg is; `printf -v` en niet `eval`.
    if [[ -z "${!doel:-}" ]]; then
      printf -v "$doel" '%s' "$waarde"
      export "${doel?}"
      echo "    ${doel} ingelezen"
    fi
  done <"$pad"
}

controleer_vereisten() {
  if ! command -v kubectl >/dev/null 2>&1; then
    err "kubectl niet gevonden"
    exit 2
  fi
  # Alleen verplicht als het oauth-Secret er nog niet is. Stond hij er al, dan zou dit
  # script je dwingen een correct werkend clientsecret opnieuw uit Keycloak te halen om
  # de ándere Secrets te kunnen aanmaken — en dan doet iemand het met de hand, wat
  # precies de reproduceerbaarheid weghaalt waarvoor dit script bestaat.
  if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
    if kubectl -n "$NAMESPACE" get secret iso-audit-portal-oauth >/dev/null 2>&1; then
      SKIP_OAUTH=true
      return 0
    fi
    err "KEYCLOAK_CLIENT_SECRET is verplicht — zonder dit start de oauth2-proxy niet."
    err "Haal hem uit Keycloak: realm commonground, client iso-audit-portal, tab Credentials."
    err "Bestaat het Secret al, dan mag je hem weglaten; dit script laat hem dan staan."
    exit 2
  fi
}

maak_oauth_secret() {
  local cookie_secret
  if [[ "${SKIP_OAUTH:-false}" == true ]]; then
    echo "  bestaat al en geen KEYCLOAK_CLIENT_SECRET meegegeven — ongemoeid gelaten."
    echo "  Roteren doe je met KEYCLOAK_CLIENT_SECRET erbij, of via rollout-portal.sh."
    return 0
  fi
  # 32 bytes, URL-SAFE base64. De `tr` is niet cosmetisch: oauth2-proxy decodeert
  # het cookie-secret met base64.RawURLEncoding, en die verwerpt de tekens `+` en
  # `/` uit standaard-base64. Mislukt het decoderen, dan leest oauth2-proxy de
  # string als 44 ruwe bytes en faalt met
  #   "cookie_secret must be 16, 24, or 32 bytes ..., but is 44 bytes".
  # Dat duwde de eerste rollout om (2026-08-12) en is niet aan het secret te zien —
  # alleen aan de crashloop van de proxy.
  cookie_secret="$(openssl rand -base64 32 | tr -- '+/' '-_')"
  # 32 bytes → 43 tekens data + één '='-padding. Faal hier, niet in het cluster.
  if [[ ! "$cookie_secret" =~ ^[A-Za-z0-9_-]{43}=$ ]]; then
    err "gegenereerd cookie-secret heeft een onverwachte vorm; niets toegepast"
    exit 3
  fi
  apply_secret "iso-audit-portal-oauth" \
    --from-literal="client-secret=${KEYCLOAK_CLIENT_SECRET}" \
    --from-literal="cookie-secret=${cookie_secret}"
  echo "  let op: het cookie-secret is nieuw gegenereerd. Bestaande sessies zijn"
  echo "  daarmee ongeldig — dat is precies wat je wil bij een rotatie."
}

maak_llm_secret() {
  if [[ -z "${ANTHROPIC_KEY:-}" ]]; then
    echo "  ANTHROPIC_KEY niet gezet — overgeslagen. Triage en memo werken; de"
    echo "  LLM-classificatie niet."
    return 0
  fi
  apply_secret "iso-audit-portal-llm" --from-literal="api-key=${ANTHROPIC_KEY}"
}

maak_sources_secret() {
  local -a args=()
  [[ -n "${JIRA_BASE_URL:-}" ]] && args+=(--from-literal="jira-base-url=${JIRA_BASE_URL}")
  [[ -n "${JIRA_USER_EMAIL:-}" ]] && args+=(--from-literal="jira-user-email=${JIRA_USER_EMAIL}")
  [[ -n "${JIRA_API_TOKEN:-}" ]] && args+=(--from-literal="jira-api-token=${JIRA_API_TOKEN}")
  [[ -n "${MIRO_API_TOKEN:-}" ]] && args+=(--from-literal="miro-api-token=${MIRO_API_TOKEN}")

  if [[ ${#args[@]} -eq 0 ]]; then
    echo "  geen bron-credentials gezet — overgeslagen. /config/health meldt de"
    echo "  bronnen dan als niet-gekoppeld; de pod start gewoon."
    return 0
  fi
  apply_secret "iso-audit-portal-sources" "${args[@]}"
}

maak_google_secret() {
  if [[ -z "${GOOGLE_SA_FILE:-}" ]]; then
    # Bewust een waarschuwing en geen stille overslag: Drive en de auditplanning lezen
    # sinds 2026-08-15 via dit service-account. Zonder dit Secret is de mount leeg
    # (`optional: true` in deployment.yaml) en melden beide bronnen zich in het portaal
    # als niet-gekoppeld — zonder dat iemand ziet dát er een Secret ontbreekt.
    echo "  LET OP: GOOGLE_SA_FILE niet gezet — overgeslagen." >&2
    echo "  Drive en de auditplanning werken dan NIET; ze verschijnen in het portaal" >&2
    echo "  als 'niet gekoppeld'. Dit is de enige credential die een auditor niet zelf" >&2
    echo "  in de UI kan zetten: het is een gemount bestand, geen env-var." >&2
    return 0
  fi
  if [[ ! -f "$GOOGLE_SA_FILE" ]]; then
    err "GOOGLE_SA_FILE bestaat niet: ${GOOGLE_SA_FILE}"
    exit 2
  fi
  # Controleer het type vóór het aanmaken: een `authorized_user`-JSON (uit een
  # OAuth-login) is persoonsgebonden en werkt niet met `service_account.Credentials`.
  local soort
  soort="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("type",""))' \
    "$GOOGLE_SA_FILE" 2>/dev/null || true)"
  if [[ "$soort" != "service_account" ]]; then
    err "GOOGLE_SA_FILE is geen service-account-keyfile (type=${soort:-onbekend})."
    err "Een 'authorized_user'-bestand hoort bij een persoon en is precies wat deze"
    err "migratie wegneemt. Vraag een keyfile van het org-service-account."
    exit 2
  fi
  apply_secret "iso-audit-portal-google" \
    --from-file="service-account.json=${GOOGLE_SA_FILE}"
}

main() {
  parse_args "$@"
  echo "waarden verzamelen…"
  lees_env_bestand "$ENV_FILE"
  controleer_vereisten

  echo "namespace ${NAMESPACE} controleren…"
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  echo "1/4 oauth2-proxy"
  maak_oauth_secret
  echo "2/4 LLM-key"
  maak_llm_secret
  echo "3/4 bron-credentials"
  maak_sources_secret
  echo "4/4 Google-service-account"
  maak_google_secret

  echo
  echo "klaar. Aanwezige Secrets:"
  kubectl get secrets --namespace "$NAMESPACE" \
    --no-headers -o custom-columns=NAAM:.metadata.name,LEEFTIJD:.metadata.creationTimestamp
  echo
  echo "Denk aan de herleidbaarheidstabel in deploy/README.md: elke credential"
  echo "hoort org-owned te zijn, met info@conduction.nl als eigenaar-rol en een"
  echo "vastgelegde maximale leeftijd. Een credential op naam van een persoon"
  echo "hoort hier niet."
}

main "$@"
