## Wat verandert er?

<!-- Eén of twee zinnen. Niet de implementatie — het effect. -->

## Waarom

<!-- Motivatie. Verwijs naar issue, change-proposal of capability uit docs/explanation/missie.md. -->

Closes #

## Type wijziging

- [ ] Bugfix (non-breaking)
- [ ] Feature (non-breaking)
- [ ] Breaking change
- [ ] Refactor / cleanup
- [ ] Docs / configuratie
- [ ] Source-adapter (zie source-adapter issue-template checklist)
- [ ] Notifier-adapter (zie notifier-adapter issue-template checklist)

## Checklist

- [ ] Tests toegevoegd of bestaande tests dekken de wijziging
- [ ] CHANGELOG.md bijgewerkt onder `[Unreleased]`
- [ ] Breaking changes expliciet gemarkeerd in commit-message én CHANGELOG
- [ ] Geen secrets in code, logs, tests of docs (gitleaks groen)
- [ ] CI-jobs lokaal groen vóór push: `uv run ruff check .`, `ruff format --check`, `mypy --strict`, `bandit -r src`, `pytest`

## Missie-impact

<!-- Versterkt deze PR een van de drie capabilities uit docs/explanation/missie.md? Of is
     het pure operatie? Beide zijn legitiem; missie-impact noteren maakt het
     spoor over tijd zichtbaar. -->

- [ ] Capability 1 — onafhankelijke bronnen
- [ ] Capability 2 — patroondetectie
- [ ] Capability 3 — auditor-spiegel
- [ ] Operationeel
