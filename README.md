# EdgeVector org defaults

Org-wide defaults for `EdgeVector/*` repos: shared community files and
reusable GitHub Actions workflows.

## Reusable workflows

### `auto-merge.yml`

Flips on `--auto` (auto-merge) for the calling repo's PR so the merge queue
picks it up when CI passes. Replaces the per-repo `auto-merge.yml`
duplicates that previously lived in every consuming repo.

Each consuming repo's local `.github/workflows/auto-merge.yml` is now a
~6-line stub that calls this:

```yaml
name: Auto-merge
on:
  pull_request:
    types: [opened, reopened, synchronize]

permissions:
  contents: write
  pull-requests: write

jobs:
  call:
    uses: EdgeVector/.github/.github/workflows/auto-merge.yml@main
    secrets: inherit
```

The `permissions:` block is required — without it the caller's `GITHUB_TOKEN`
defaults to read-only and the called workflow startup-fails when it tries to
request `contents: write` / `pull-requests: write`. (The reusable workflow
caps at those scopes; declaring them in the caller is what actually grants
them.)

`secrets: inherit` carries the org-level `GH_PAT` through the call.

**Prerequisites for consuming repos:**

- A `default-branch-merge-queue` repository ruleset on `main` (without it,
  `gh pr merge --auto` is rejected by gh CLI for needing an explicit
  method flag — the queue is what lets gh defer method to its config).
- `GH_PAT` reachable as an org-level Actions secret.

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

### `manage-org-secret.yml`

Manual `workflow_dispatch` for creating or rotating EdgeVector org-level
Actions secrets. Runs inside `EdgeVector/.github`, where `GH_PAT` is
available with the admin scope needed to write org secrets. Kept around
for future rotations rather than deleted after first use.

```bash
gh workflow run manage-org-secret.yml \
  --repo EdgeVector/.github \
  -f secret_name=SOME_NAME \
  -f secret_value='...'
```
