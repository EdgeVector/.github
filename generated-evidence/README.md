# Generated evidence policy

Raw operational output stays outside Git. This rule applies to every EdgeVector repo.
It includes logs, samples, request/reply dumps, generated receipts, and compressed copies.

Use the CI summary and workflow artifacts as the validation record. Link the run in the PR.
Routine CI needs no separate committed report or `artifact.json`. This rule replaces older
instructions to commit proof files. Keep useful source scripts and durable design conclusions
in Git. A deliberate report can state the result, method, revisions, commands, and limits.
CI records the download URL, checksum, source revision, and expiration beside the result.
Use a durable archive for selected results that need long retention. Verify retained output before cleanup.

Optional evidence files have a limit of 10 changed files and 100,000 total bytes per PR.
The check counts each changed file's complete size. It checks the committed Git files,
so ignore rules and force-add cannot override it. Unchanged historical files and deletions
do not count. Product JSON configuration and source scripts stay outside this budget.

Evidence directories include `proofs`, `evidence`, `receipts`, `captures`, `measurements`,
`benchmark-results`, `bench-results`, and `raw-http`. Benchmark result/output directories
also count. Raw log suffixes and named sample/dump files are blocked outside those directories.
Evidence directories permit Markdown and source scripts. They also permit one optional compact
`artifact.json` per directory. No report or receipt is required for a PR to pass this check.
The check inspects committed files; it does not certify a CI run or benchmark result.
When a receipt is necessary for a durable archive, it uses these string fields:

```json
{
  "url": "https://example.com/download/evidence.zip",
  "sha256": "<64 hexadecimal characters>",
  "source_revision": "<full Git source revision>",
  "command": "<reproduction command>",
  "expires_at": "<date or retention policy>",
  "note": "<optional limits>"
}
```

The URL, checksum, and source revision are required. The receipt limit is 4096 bytes.
Do not include raw values, local file inventories, or credentials in the receipt.

An intentional product data file can use an exact-path exception in
`.github/generated-evidence-policy.json`. Add the exception in a separate reviewed PR first.
The check reads exceptions from the accepted base, never from the candidate.
The exception does not increase the evidence budget or exempt generated output by category.

```json
{"product_data": [{"path": "data/example-samples.json", "reason": "Published product sample data"}]}
```

Local check from the candidate repo:

```bash
python3 /path/to/this/action/check.py --base origin/main --head HEAD
```

The action needs the base and candidate Git history. It reads blobs and does not execute
candidate code. A read-only token is sufficient. Use the same check for PRs and merge groups.
