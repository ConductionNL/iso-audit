---
status: current
last_reviewed: 2026-08-17
---

# Configuration precedence

> **Why the API prefix is `/instellingen/` and not `/config/`.** Do not "tidy" this back.
> The shared nginx ingress controller carries a global Nextcloud hardening snippet with
> `location ~ ^/(?:build|tests|config|lib|3rdparty|templates|data)/ { deny all; }`. It
> applies to every host on the cluster, so every request under `/config/` was answered with
> nginx's own 403 and never reached the pod — invisible in both the application and the
> oauth2-proxy logs. Measured 2026-08-17; the same snippet also blocks any path starting
> with `autotest`, `occ`, `issue`, `indie`, `db_` or `console` (no trailing slash, so
> `/issues` and `/indienen` match too). Renaming our own routes is the only fix that does
> not touch infrastructure shared with other tenants.

All configuration is resolved by one loader, `iso_audit.config.settings.load_config`.
Nothing reads `os.environ` directly for configuration: that would lose the provenance,
and provenance is the part an auditor asks about.

## Order

| Priority | Source | Intended for |
|---|---|---|
| 1 (wins) | environment | Secrets and per-environment values. Injected by the deployment, CI, or a `.env` on a workstation. |
| 2 | `config.yaml` | Non-secret defaults you want in version control — a Jira URL, a model choice. |
| 3 | UI store | What an auditor links in the portal. |
| 4 | built-in default | Only where a sensible default exists (currently the model). |

The first source with a non-empty value wins. An empty or whitespace-only value does not
count as set, so it never blocks a lower source.

**Why environment first.** A deployment must never silently run on a value someone typed
into the UI. Conversely, if the UI could override the manifest, an auditor could change a
deployment without it being visible in Git.

## Provenance

Every resolved value carries its own source (`ui-override`, `env`, `yaml`, `ui`,
`default`, `leeg`). Provenance is a property of the value, not a separate bookkeeping
table — that way it cannot fall away between resolving and using.

- At startup, one audit-log line per field records which source won. Never the value.
- `GET /instellingen/herkomst` returns the same information, so an auditor can check it without
  cluster access.
- In the portal, each input shows a badge with its source. Fields set from the environment
  or `config.yaml` are read-only, because a value typed over them would have no effect.

## Overriding an administrator value

A field set from the environment can still be replaced from the portal, but only as an
**explicit** action (`POST /instellingen/bronnen/{bron}?overschrijf=true`). Its provenance then
becomes `ui-override`, and the change trail records `overschrijft_omgeving: true` with who
and when — never the value. Clearing the field restores the environment value.

This exists for one reason: a credential that expires or is revoked must be replaceable by
the person doing the audit. If that requires a cluster administrator, the audit capability
is tied to one person again — see
[`credential-rotatie-door-auditor`](../../openspec/changes/credential-rotatie-door-auditor/proposal.md).

If the environment value changes *after* an override was made — an administrator rotating
a Secret, for instance — the portal says so on that field. The override stays in effect
until someone removes it; the comparison uses a fingerprint, so neither value is shown.

## Secrets

- A secret value is never returned by the API, never written to a log, and never shown in
  the text representation of the object holding it — `repr()` prints `<geheim>` and the
  source. That is a structural boundary, not a discipline: a secret cannot reach a log
  file through an f-string or a stack trace.
- Where the UI shows an existing secret it is masked with a fixed-length prefix, so the
  masking does not reveal the length of the token.
- A secret in `config.yaml` works, but logs a warning. Refusing to start would block a
  third party on a file they can fix themselves; making it visible is enough.

## Schema version

`config_version` is explicit so a future migration is traceable. A file carrying a higher
version than the code knows is reported and then read anyway — an auditor who cannot see
their configuration cannot repair it either.

## Anthropic auth modes

| | `api_key` | `sso` |
|---|---|---|
| Classification, themes, memo text | yes | yes |
| Headless (cron, CI, a runtime in the cluster) | yes | no — needs a browser step, and the refresh token hard-expires |
| Cost traceable on an organisation invoice | yes | no — runs on a personal subscription |

`sso` uses the Anthropic CLI profile, which the SDK already resolves as a credential
source; no second call path exists for the classifier.

**One trap worth knowing.** A set `ANTHROPIC_API_KEY` takes precedence over the CLI
profile — *including an empty string*. In `sso` mode the loader therefore removes that
variable from the environment rather than merely skipping it. Without that, a run fails on
a credential the auditor did not choose, and the error points at Anthropic instead of at
the configuration.

Because `sso` is personal by definition, it is a working step for interactive use, not an
end state for an organisation that wants the capability to outlive one person.

## Model choice and cost

The model is configurable, default `claude-haiku-4-5`. Every selectable model must have a
price row; a test fails otherwise. A model without a price row would make a run report a
cost of zero — worse than no cost line, because it looks complete.

Rates carry a review date (`PRIJZEN_PEILDATUM`) because prices change outside this repo.
