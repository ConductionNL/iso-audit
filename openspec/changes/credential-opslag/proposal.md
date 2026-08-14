# Change: credential-opslag

## Why

UI-configuratie stond als platte JSON op de PVC. Dat werkt, maar een cluster-Secret is de
plek waar een beheerder credentials verwacht, met RBAC en kube-API-auditlogging eromheen.

Deze change is bewust losgetrokken van `configureerbare-credentials`: het is de enige stap
die de app kube-API-toegang geeft, en die moet apart te reviewen en apart te verifiëren zijn.

## What Changes

- Secret-backend achter de bestaande `BronConfig`-interface; PVC blijft als terugval.
- `deploy/rbac-config.yaml`: Role + RoleBinding op **één Secret-naam**, `get`+`patch`.
- Projected serviceaccount-token, alleen in de app-container, 1 uur geldig.

## Scope-grens

- **Geen** wijziging aan de publieke methodes van `BronConfig`.
- **Geen** `automountServiceAccountToken: true`. Dat zou de token ook aan de
  oauth2-proxy-sidecar geven.
- **Geen** eigen sleutelbeheer of encryptielaag. Dit is geen secret-manager.
