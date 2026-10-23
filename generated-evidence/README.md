# Generated evidence policy

Raw operational output stays outside Git. This rule applies to every EdgeVector repo.
It includes logs, samples, request/reply dumps, generated receipts, and compressed copies.

Commit a short Markdown report and useful source scripts. The report states the result,
method, source revisions, commands, and limits. Link the raw output when review needs it.
Keep CI output as a workflow artifact. Use a durable archive for long retention.
Record an expiration date when the download expires. Verify the upload before local cleanup.

Each PR permits at most 10 changed evidence files and 100,000 total evidence bytes.
The check counts each changed file's complete size. It checks the committed Git files,
so ignore rules and force-add cannot override it. Unchanged historical files and deletions
do not count. Product JSON configuration and source scripts stay outside this budget.

Evidence directories include `proofs`, `evidence`, `receipts`, `captures`, `measurements`,
`benchmark-results`, `bench-results`, and `raw-http`. Benchmark result/output directories
also count. Raw log suffixes and named sample/dump files are blocked outside those directories.
Evidence directories permit Markdown and source scripts. They also permit one compact
`artifact.json` per directory. It must use these string fields:

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
