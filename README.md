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
jobs:
  call:
    uses: EdgeVector/.github/.github/workflows/auto-merge.yml@main
    secrets: inherit
```

`secrets: inherit` carries the org-level `GH_PAT` through the call.

**Prerequisites for consuming repos:**

- A `default-branch-merge-queue` repository ruleset on `main` (without it,
  `gh pr merge --auto` is rejected by gh CLI for needing an explicit
  method flag — the queue is what lets gh defer method to its config).
- `GH_PAT` reachable as an org-level Actions secret.
