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
# shell-history en in de procestabel) maar uit env-vars.
#
# Writes: Secrets iso-audit-portal-{oauth,llm,sources,google} in iso-platform
# Idempotent: ja — apply van een gegenereerd manifest
# Requires: kubectl met toegang tot het cluster, openssl
# Style-afwijking: geen
#
# Usage:
#   # minimaal — alleen oauth2-proxy (verplicht om de pod te laten starten):
#   KEYCLOAK_CLIENT_SECRET='...' ./scripts/create-portal-secrets.sh
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

controleer_vereisten() {
  if ! command -v kubectl >/dev/null 2>&1; then
    err "kubectl niet gevonden"
    exit 2
  fi
  if [[ -z "${KEYCLOAK_CLIENT_SECRET:-}" ]]; then
    err "KEYCLOAK_CLIENT_SECRET is verplicht — zonder dit start de oauth2-proxy niet."
    err "Haal hem uit Keycloak: realm commonground, client iso-audit-portal, tab Credentials."
    exit 2
  fi
}

maak_oauth_secret() {
  local cookie_secret
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
    echo "  GOOGLE_SA_FILE niet gezet — overgeslagen (komt met de change"
    echo "  gsuite-service-account-sources)."
    return 0
  fi
  if [[ ! -f "$GOOGLE_SA_FILE" ]]; then
    err "GOOGLE_SA_FILE bestaat niet: ${GOOGLE_SA_FILE}"
    exit 2
  fi
  apply_secret "iso-audit-portal-google" \
    --from-file="service-account.json=${GOOGLE_SA_FILE}"
}

main() {
  controleer_vereisten

  echo "namespace ${NAMESPACE} controleren…"
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  echo "1/4 oauth2-proxy (verplicht)"
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
