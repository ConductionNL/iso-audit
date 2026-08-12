---
status: draft
last_reviewed: 2026-07-13
---

# iso-audit documentation

iso-audit is a pluggable ISO 9001 + ISO 27001 audit pipeline, built as a
structural mitigation for the auditor role-conflict that ISO 19011 §6.4.2
recognises: it draws evidence from sources the auditor does not curate, detects
patterns across runs, and mirrors auditor decisions back for reflection. For the
project overview, setup, and current milestone status, start at the
[README](../README.md); the *why* behind the design lives in
[explanation/missie.md](explanation/missie.md).

> **Status:** milestone A. Most pages below are migrated from the old flat
> `docs/` layout and carry `status: draft` until reviewed. Several pages are
> written in Dutch — the language decision is deferred to the maintainer (see
> the PR that introduced this contract).

## Sections

- **how-to/** — task-oriented guides:
  - [Set up a Miro auditor board via Miro-AI](how-to/miro-auditor-bord-prompt.md)
  - [Interview flow without Python automation](how-to/miro-interview-prompt.md)
  - [Verify portal fail-closed auth without a cluster](how-to/verify-portal-auth.md)
- **reference/** — facts about protocols, adapters, and configuration:
  - [Pipeline modes (autonoom / integer)](reference/modes.md)
  - Sources: [Drive](reference/source-drive.md) · [Planning](reference/source-planning.md) · [Jira](reference/source-jira.md) · [MCP](reference/source-mcp.md) · [REST](reference/source-rest.md)
  - [Sinks](reference/sinks.md)
  - Notifiers: [Slack](reference/notifier-slack.md) · [Email](reference/notifier-email.md) · [Teams](reference/notifier-teams.md) · [Mattermost](reference/notifier-mattermost.md)
- **explanation/** — design decisions and rationale:
  - [Missie — why this tool exists (three capabilities)](explanation/missie.md)
  - [Auditmemo architecture](explanation/memo-architecture.md)
  - [Compensating control — audit log](explanation/compensating-control.md)
  - [Portal auth — why the identity header is trustworthy](explanation/portal-auth.md)
