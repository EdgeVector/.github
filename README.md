# EdgeVector org defaults

Org-wide defaults for `EdgeVector/*` repos: shared community files and
reusable GitHub Actions workflows.

## Repository venue

`EdgeVector/.github` is intentionally GitHub-primary. It is an exception to the
public LastGit dual-home pattern because its reusable workflows are consumed by
other repositories with `uses: EdgeVector/.github/.github/workflows/...@main`,
and because the org-level `GH_PAT` health probe must run as a scheduled GitHub
Actions workflow.

Do not convert this repository into a read-only GitHub mirror unless every
consumer has moved off the GitHub `uses:` path and the scheduled org probe has a
replacement venue. The normal public-repo LastGit pattern still applies to repos
whose GitHub copy is only for cloning and browsing.

## Reusable workflows

### `discord-notify.yml`

Posts custom Discord embeds for push / pull_request / issues /
issue_comment events. Replaces the per-repo `discord-notify.yml`
duplicates that previously lived in every consuming repo.

The reusable workflow takes no inputs — the caller's `on:` list decides
which events to forward (this is how `workflow_call` works; the reusable
workflow itself doesn't run on repository events).

Each consuming repo's local `.github/workflows/discord-notify.yml` is now
a ~20-line stub that calls this:

```yaml
name: Discord Notifications
on:
  push:
    branches: [main]
  pull_request:
    types: [opened, closed, reopened]
  issues:
    types: [opened, closed, reopened]
  issue_comment:
    types: [created]

permissions: {}

jobs:
  call:
    uses: EdgeVector/.github/.github/workflows/discord-notify.yml@main
    secrets: inherit
```

`secrets: inherit` carries the org-level `DISCORD_WEBHOOK_URL` through.

**Prerequisites for consuming repos:**

- `DISCORD_WEBHOOK_URL` reachable as an org-level Actions secret. The
  payload is a custom embed (not Discord's native `/github` integration
  format), so the secret must be the bare Discord webhook URL — not the
  `?wait=true` or `/github` suffix variants.
