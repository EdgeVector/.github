# EdgeVector org defaults

Org-wide defaults and SHA-pinned GitHub Actions composite policy checks for `EdgeVector/*` repositories.

The public LastDB URL is https://thelastdb.com.
First-run LastDB install instructions are at https://thelastdb.com/llms.txt.

## Shared SHA-pinned CI policy actions

Callers pin these composite actions by full 40-character commit SHA so repository PRs cannot weaken policy gates inline:

- `EdgeVector/.github/generated-evidence@<sha>` — reject committed logs, raw dumps, and oversized generated evidence.
- `EdgeVector/.github/secret-scan@<sha>` — scan tracked text files for high-confidence secrets without printing values.
- `EdgeVector/.github/no-build-artifacts@<sha>` — block build/cache trees (`target/`, `node_modules/`, `__pycache__/`) and blobs over 2 MiB.
- `EdgeVector/.github/source-diff-policy@<sha>` — enforce changed source file-size caps, touched Rust function-size caps, and `clippy::too_many_arguments` ratchets on PR diffs.
- `EdgeVector/.github/layer-check@<sha>` — enforce intra-crate Rust module layer order declared in `<crate>/layers.toml`.
- `EdgeVector/.github/install-ripgrep@<sha>` — install SHA-256-verified `ripgrep` 14.1.0 onto `$GITHUB_PATH` when absent.

## Shared app CI on a real LastDB node

- `EdgeVector/.github/lastdb-node@<sha>` — download the newest `EdgeVector/lastdb` nightly, verify its checksums, and start it on a fresh empty home. An app's job then runs its real commands against the socket in `LASTDB_SOCKET_PATH` (also the `socket` output). The job summary records the nightly tag, source commit, checksum, API version and home marker. Linux x86_64 runners only.

```yaml
steps:
  - uses: actions/checkout@<sha>
  - uses: EdgeVector/.github/lastdb-node@<sha>
  - run: python3 scripts/ci-lastdb-node.py   # the app's own script
```

A job that starts its own nodes passes `start: "false"`. The action then only downloads and verifies, and the job reads the `lastdbd`, `lastdb`, `tag`, `revision`, `version` and `sha256` outputs.

The node holds generated data only and ends with the job. The home allows `POST /api/schemas/seed-system` with `isolated_copy: true`, so a job can declare its own schemas.

Factory: ship-feature-v4-gate live since 2026-08-26 (design gate + review loop)
