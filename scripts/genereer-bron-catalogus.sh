#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: installer
#
# scripts/genereer-bron-catalogus.sh — schrijf de bron-catalogus als YAML.
#
# De catalogus bepaalt welke velden een auditor per bron in de UI invult: label, hint,
# en of een veld geheim is. Een beheerder draait dit één keer bij initialisatie en past
# daarna het YAML-bestand aan; de auditor hoeft niets van env-vars of Secrets te weten.
#
# Zonder dit bestand werkt het portaal ook: dan geldt de ingebouwde standaard uit
# `src/iso_audit/api/bron_catalogus.py`. Het bestand is dus een aanpassing, geen
# voorwaarde — en dat is bewust, want een tool dat pas werkt na een generatiestap is
# geen tool dat je aan derden levert.
#
# Writes: het opgegeven YAML-pad (default config/bronnen.yaml); overschrijft niet
#         zonder --force
# Idempotent: ja — zonder --force laat het een bestaand bestand staan
# Requires: uv (en dit script vanuit de repo-root draaien)
# Style-afwijking: geen
#
# Usage:
#   ./scripts/genereer-bron-catalogus.sh                      # -> config/bronnen.yaml
#   ./scripts/genereer-bron-catalogus.sh --uit /etc/iso/b.yaml # ander pad
#   ./scripts/genereer-bron-catalogus.sh --force               # bestaand bestand vervangen
#   ./scripts/genereer-bron-catalogus.sh --stdout              # alleen tonen
#
# Daarna wijst het portaal ernaar met:
#   ISO_AUDIT_BRON_CATALOGUS=/pad/naar/bronnen.yaml

set -euo pipefail

UIT="config/bronnen.yaml"
FORCE=false
NAAR_STDOUT=false

err() { echo "error: $*" >&2; }

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --uit)
      UIT="${2:?--uit vraagt een pad}"
      shift
      ;;
    --force) FORCE=true ;;
    --stdout) NAAR_STDOUT=true ;;
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

main() {
  parse_args "$@"

  if ! command -v uv >/dev/null 2>&1; then
    err "uv niet gevonden — dit script leest de catalogus via de projectcode"
    exit 2
  fi

  local yaml
  yaml="$(uv run python -c 'from iso_audit.api.bron_catalogus import naar_yaml; print(naar_yaml(), end="")')"

  if [[ "$NAAR_STDOUT" == true ]]; then
    printf '%s' "$yaml"
    return 0
  fi

  if [[ -f "$UIT" && "$FORCE" != true ]]; then
    err "${UIT} bestaat al. Gebruik --force om te vervangen, of --stdout om te vergelijken."
    exit 3
  fi

  mkdir -p "$(dirname "$UIT")"
  printf '%s' "$yaml" >"$UIT"
  echo "geschreven: ${UIT}"
  echo
  echo "Wijs het portaal ernaar met:"
  echo "  ISO_AUDIT_BRON_CATALOGUS=$(realpath "$UIT")"
  echo
  echo "Let op: de veldnamen zijn de env-vars die de adapters lezen. Hernoem ze niet,"
  echo "want dan koppelt de bron niet meer. Labels en hints zijn wél vrij aan te passen."
}

main "$@"
