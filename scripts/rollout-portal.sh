#!/usr/bin/env bash
# SPDX-License-Identifier: EUPL-1.2
# role: tool
#
# scripts/rollout-portal.sh — breng het iso-audit-portaal van commit naar draaiend.
#
# Doet de hele keten in één run: pushen, wachten tot het image gebouwd is, mergen,
# wachten tot Argo de nieuwe revisie heeft, het cookie-secret roteren, herstarten en
# verifiëren. Elke stap controleert zijn eigen resultaat en stopt bij een fout in
# plaats van door te denderen.
#
# Werkt zowel vanaf een branch (pusht, PR, merge) als direct vanaf main (dan alleen
# pushen en verder). Op main is er een kort venster waarin Argo de nieuwe tag al ziet
# terwijl het image nog gebouwd wordt; het script wacht daarom eerst op de build en
# doet de herstart pas daarna.
#
# Het cookie-secret wordt in plaats geroteerd met een patch, zodat het
# Keycloak-clientsecret dat al in het cluster staat niet opnieuw nodig is.
#
# Writes: Secret iso-audit-portal-oauth (alleen de key cookie-secret),
#         Deployment iso-audit-portal (restart), git remote, GitHub PR
# Idempotent: ja — opnieuw draaien rotteert het cookie-secret nogmaals en herstart
# Requires: git, gh (ingelogd), kubectl (toegang tot het cluster), openssl, jq
# Style-afwijking: geen
#
# Usage:
#   ./scripts/rollout-portal.sh                   # volledige keten
#   ./scripts/rollout-portal.sh --dry-run         # alleen tonen wat er zou gebeuren
#   ./scripts/rollout-portal.sh --skip-secret     # niet roteren (secret is al goed)
#   ./scripts/rollout-portal.sh --skip-merge      # push + build, niet mergen

set -euo pipefail

readonly REPO="ConductionNL/iso-audit"
readonly NS="iso-platform"
readonly DEPLOY="iso-audit-portal"
readonly HOST="iso.commonground.nu"
readonly PKG="orgs/ConductionNL/packages/container/iso-audit/versions"

DRY_RUN=false
SKIP_SECRET=false
SKIP_MERGE=false

err() { echo "error: $*" >&2; }
stap() {
  echo
  echo "=== $*"
}
doe() {
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] $*"
  else
    "$@"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
    --dry-run) DRY_RUN=true ;;
    --skip-secret) SKIP_SECRET=true ;;
    --skip-merge) SKIP_MERGE=true ;;
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

controleer_vereisten() {
  local ontbreekt=()
  for cmd in git gh kubectl openssl jq; do
    command -v "$cmd" >/dev/null 2>&1 || ontbreekt+=("$cmd")
  done
  if [[ ${#ontbreekt[@]} -gt 0 ]]; then
    err "ontbrekende tools: ${ontbreekt[*]}"
    exit 2
  fi
  if [[ -n "$(git status --porcelain)" ]]; then
    err "werkboom is niet schoon. Commit of stash eerst — dit script pusht wat er staat."
    exit 2
  fi
}

# De tag die Argo gaat pullen, plus de controle die de CI ook doet.
lees_versie() {
  local versie tag
  versie="$(grep -m1 '^version = ' pyproject.toml | cut -d'"' -f2)"
  tag="$(grep -m1 'newTag:' deploy/kustomization.yaml | cut -d'"' -f2)"
  if [[ "$versie" != "$tag" ]]; then
    err "pyproject version (${versie}) en kustomization newTag (${tag}) lopen uiteen."
    err "Zet ze gelijk; anders faalt de image-workflow toch."
    exit 2
  fi
  echo "$versie"
}

wacht_op_image() {
  local tag="$1"
  stap "wachten tot ghcr-tag ${tag} bestaat"
  for _ in $(seq 1 60); do
    if gh api "$PKG" --jq '[.[].metadata.container.tags]|flatten|join(" ")' 2>/dev/null |
      tr ' ' '\n' | grep -Fxq "$tag"; then
      echo "  tag ${tag} staat in de registry"
      return 0
    fi
    sleep 15
  done
  err "tag ${tag} is na 15 minuten nog niet gepubliceerd. Check: gh run list --repo ${REPO}"
  exit 1
}

push_en_merge() {
  local branch="$1" nr
  stap "pushen van ${branch}"
  doe git push -u origin "$branch"

  [[ "$branch" == "main" ]] && {
    echo "  op main — geen PR nodig"
    return 0
  }
  [[ "$SKIP_MERGE" == true ]] && {
    echo "  --skip-merge: PR niet gemerged"
    return 0
  }

  stap "PR openen of hergebruiken"
  nr="$(gh pr list --repo "$REPO" --head "$branch" --state open --json number --jq '.[0].number' 2>/dev/null || true)"
  if [[ -z "$nr" || "$nr" == "null" ]]; then
    doe gh pr create --repo "$REPO" --base main --head "$branch" \
      --title "chore: rollout $(lees_versie)" \
      --body "Aangemaakt door scripts/rollout-portal.sh."
    nr="$(gh pr list --repo "$REPO" --head "$branch" --state open --json number --jq '.[0].number' 2>/dev/null || echo "")"
  fi
  echo "  PR #${nr}"

  stap "mergen van PR #${nr}"
  doe gh pr merge "$nr" --repo "$REPO" --merge --delete-branch
}

# Wacht tot Argo gesynct is OP DE COMMIT DIE WE NET GEPUSHT HEBBEN.
#
# Alleen op "Synced" wachten is niet genoeg en dat is precies wat er misging op
# 2026-08-12: Argo stond al Synced op de vórige revisie, dus de wacht viel er
# meteen door, waarna de herstart met het oude manifest liep en de nieuwe
# initContainer ontbrak. Argo pollt standaard om de ~3 minuten; we forceren een
# refresh en vergelijken de revisie.
wacht_op_argo() {
  local want="$1" rev sync health
  stap "wachten tot Argo gesynct is op ${want:0:12}"
  doe kubectl annotate application "$DEPLOY" -n argocd \
    argocd.argoproj.io/refresh=normal --overwrite
  for _ in $(seq 1 40); do
    rev="$(kubectl get application "$DEPLOY" -n argocd -o jsonpath='{.status.sync.revision}' 2>/dev/null || true)"
    sync="$(kubectl get application "$DEPLOY" -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
    health="$(kubectl get application "$DEPLOY" -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
    echo "  rev=${rev:0:12} sync=${sync:-?} health=${health:-?}"
    if [[ "$sync" == "Synced" && "$rev" == "$want" ]]; then
      return 0
    fi
    sleep 15
  done
  err "Argo staat na 10 minuten niet op ${want:0:12}. Check: kubectl describe application ${DEPLOY} -n argocd"
  exit 1
}

# In plaats: alleen de key cookie-secret. Het clientsecret staat al in het cluster
# en hoeft dus niet opnieuw door de hand van een mens.
roteer_cookie_secret() {
  local cookie patch
  stap "cookie-secret roteren"

  cookie="$(openssl rand -base64 32 | tr -- '+/' '-_')"
  # URL-safe én de juiste lengte; oauth2-proxy decodeert met RawURLEncoding en
  # verwerpt + en /. Faal hier, niet in een crashloop in het cluster.
  if [[ ! "$cookie" =~ ^[A-Za-z0-9_-]{43}=$ ]]; then
    err "gegenereerd cookie-secret heeft een onverwachte vorm; niets gewijzigd"
    exit 3
  fi

  # Via een 0600-bestand op stdin-pad, niet als argument: argumenten staan in de
  # procestabel en in je shell-history.
  patch="$(umask 077 && mktemp)"
  # shellcheck disable=SC2064  # pad nu expanden, niet bij exit
  trap "rm -f '${patch}'" EXIT
  printf '{"stringData":{"cookie-secret":"%s"}}\n' "$cookie" >"$patch"

  doe kubectl patch secret iso-audit-portal-oauth -n "$NS" \
    --type merge --patch-file "$patch"
  echo "  bestaande sessies zijn hiermee ongeldig — bedoeld bij een rotatie"
}

herstart_en_verifieer() {
  stap "herstarten"
  doe kubectl -n "$NS" rollout restart "deploy/${DEPLOY}"
  doe kubectl -n "$NS" rollout status "deploy/${DEPLOY}" --timeout=300s

  stap "verifiëren"
  if [[ "$DRY_RUN" == true ]]; then
    echo "  [dry-run] curl https://${HOST}/ping"
    return 0
  fi

  # /ping is het eigen health-endpoint van oauth2-proxy en staat buiten de
  # auth-gate. /healthz van de app NIET: er is geen skip_auth_routes, dus extern
  # wordt die naar Keycloak geleid. Die check hoort daarom binnen de pod.
  # POLLEN, niet één keer proberen. `rollout status` keert terug zodra de nieuwe
  # replica available is, maar de ingress-controller heeft dan nog niet
  # noodzakelijk het nieuwe endpoint. Eén losse curl gaf daardoor twee keer een
  # valse 503 terwijl het portaal gewoon aan het opkomen was (2026-08-12).
  local code=""
  for _ in $(seq 1 20); do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "https://${HOST}/ping" 2>/dev/null || echo 000)"
    [[ "$code" == "200" ]] && break
    sleep 6
  done
  echo "  https://${HOST}/ping -> ${code}$([[ "$code" == "200" ]] && echo "" || echo "  (na 2 minuten nog niet 200 — check de proxy-logs)")"

  code="$(kubectl -n "$NS" exec "deploy/${DEPLOY}" -c app -- \
    python -c "import urllib.request as u; print(u.urlopen('http://127.0.0.1:8081/healthz').status)" \
    2>/dev/null || echo FAIL)"
  echo "  app /healthz in de pod -> ${code}"

  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "https://${HOST}/" || echo FAIL)"
  echo "  https://${HOST}/ -> ${code} (302/403 = auth-gate doet zijn werk)"
}

main() {
  parse_args "$@"
  controleer_vereisten

  local branch versie
  branch="$(git rev-parse --abbrev-ref HEAD)"
  versie="$(lees_versie)"
  echo "repo=${REPO} branch=${branch} versie=${versie} dry-run=${DRY_RUN}"

  push_en_merge "$branch"
  wacht_op_image "$versie"
  wacht_op_argo "$(git rev-parse HEAD)"
  if [[ "$SKIP_SECRET" == true ]]; then
    echo "  --skip-secret: cookie-secret ongemoeid"
  else
    roteer_cookie_secret
  fi
  herstart_en_verifieer

  stap "klaar"
  kubectl get pods -n "$NS" -l "app.kubernetes.io/name=${DEPLOY}" 2>/dev/null || true
}

main "$@"
