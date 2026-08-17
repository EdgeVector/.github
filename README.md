# EdgeVector org defaults

Org-wide defaults for `EdgeVector/*` repos (shared community files).

## Repository venue

`EdgeVector/.github` is intentionally GitHub-primary for org default files.
It is **not** a CI venue. Product repos use LastGit (`lastdb:///<slug>`) or
Forgejo; their GitHub copies are read-only mirrors with Actions disabled.
The public LastDB URL is https://thelastdb.com.

## GitHub Actions

No workflows ship from this repository. Reusable workflows that previously
lived here (`discord-notify`, `check-paths`, and the `ci-required` stub) were
removed when EdgeVector stopped using GitHub Actions for product work.

Do not re-add push/PR/scheduled workflows here unless Tom explicitly asks to
turn GitHub Actions back on.
