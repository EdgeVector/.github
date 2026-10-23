#!/usr/bin/env python3
"""Check committed PR files without executing code from the candidate tree."""

import argparse
import json
from pathlib import PurePosixPath
import re
import subprocess
import sys


MAX_BYTES = 100_000
MAX_FILES = 10
MAX_RECEIPT_BYTES = 4096
POLICY = ".github/generated-evidence-policy.json"
EVIDENCE_DIRS = {
    "proof", "proofs", "evidence", "receipts", "captures", "measurements",
    "benchmark-results", "bench-results", "benchmark-output", "bench-output",
    "perf-results", "performance-results", "raw-http", "raw-output",
    ".benchmark-output", ".evidence",
}
RAW_DIRS = {"benchmark-output", "bench-output", "raw-http", "raw-output", ".evidence", ".benchmark-output"}
SOURCE_SUFFIXES = {".py", ".sh", ".rs", ".js", ".mjs", ".cjs", ".ts", ".go"}
COMPRESSED_SUFFIXES = {".gz", ".zip", ".xz", ".bz2", ".zst", ".tar", ".7z"}
RAW_SUFFIXES = {".log", ".stdout", ".stderr", ".jsonl", ".ndjson", ".time"}
RAW_NAMES = re.compile(
    r"(?:^|[-_.])(?:samples?|receipts?|capture|dump|trace|timings?)(?:[-_.]|$)"
)
RECEIPT_KEYS = {"url", "sha256", "source_revision", "command", "expires_at", "note"}


def git(*args):
    return subprocess.check_output(["git", *args], stderr=subprocess.PIPE)


def revision(value):
    return git("rev-parse", "--verify", value + "^{commit}").decode().strip()


def changed_files(base, head):
    # --no-renames treats a move as delete + add, including a moved raw dump.
    raw = git("diff", "--name-only", "--no-renames", "--diff-filter=ACMT",
              "-z", base, head)
    return [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p]


def read_policy(base):
    # Only policy already accepted on the base can grant a product-data exception.
    try:
        raw = git("show", base + ":" + POLICY)
    except subprocess.CalledProcessError:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {"product_data"}:
        raise ValueError(POLICY + " must contain only product_data")
    entries = data["product_data"]
    if not isinstance(entries, list):
        raise ValueError("product_data must be a list of exact paths and reasons")
    allowed = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "reason"}:
            raise ValueError("each product_data entry needs path and reason")
        path, reason = entry["path"], entry["reason"]
        if not isinstance(path, str) or not isinstance(reason, str) or not reason.strip():
            raise ValueError("product_data paths and reasons must be nonempty strings")
        if path.startswith("/") or ".." in PurePosixPath(path).parts or any(c in path for c in "*?["):
            raise ValueError("product_data exceptions must use exact relative paths")
        allowed[path] = reason
    return allowed


def path_kind(path):
    name = PurePosixPath(path.lower())
    parts = set(name.parts[:-1])
    evidence = bool(parts & EVIDENCE_DIRS)
    if parts & RAW_DIRS:
        return "raw", evidence
    uncompressed = name
    while uncompressed.suffix in COMPRESSED_SUFFIXES:
        uncompressed = uncompressed.with_suffix("")
    suffix = uncompressed.suffix
    if suffix in {".log", ".stdout", ".stderr"}:
        return "raw", evidence
    if evidence:
        if name.suffix in COMPRESSED_SUFFIXES or suffix in RAW_SUFFIXES:
            return "raw", True
        if name.name == "artifact.json":
            return "receipt", True
        if name.suffix in SOURCE_SUFFIXES:
            return "product", False
        if name.suffix == ".md":
            return "summary", True
        return "raw", True
    if suffix in {".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".txt"} and RAW_NAMES.search(uncompressed.name):
        return "raw", True
    # Result directories under benchmarks are output, not benchmark source.
    if parts & {"bench", "benches", "benchmark", "benchmarks", "perf"} and parts & {"results", "output", "runs"}:
        return "raw", True
    return "product", False


def read_blob(head, path):
    spec = head + ":" + path
    size = int(git("cat-file", "-s", spec))
    return spec, size


def check_receipt(spec, size):
    if size > MAX_RECEIPT_BYTES:
        return "artifact.json exceeds 4096 bytes"
    try:
        receipt = json.loads(git("show", spec))
    except (ValueError, UnicodeError):
        return "artifact.json is not valid JSON"
    if not isinstance(receipt, dict) or not {"url", "sha256", "source_revision"} <= receipt.keys():
        return "artifact.json needs url, sha256, and source_revision"
    if set(receipt) - RECEIPT_KEYS or any(not isinstance(v, str) for v in receipt.values()):
        return "artifact.json permits only the documented string fields"
    if not receipt["url"].startswith("https://"):
        return "artifact.json needs a downloadable HTTPS URL"
    if not re.fullmatch(r"[0-9a-fA-F]{64}", receipt["sha256"]):
        return "artifact.json needs the archive SHA-256"
    if not re.fullmatch(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})", receipt["source_revision"]):
        return "artifact.json needs the full source revision"
    return None


def check(base, head):
    allowed = read_policy(base)
    evidence_bytes = 0
    evidence_files = 0
    problems = []
    paths = changed_files(base, head)
    for path in paths:
        kind, evidence = path_kind(path)
        if kind == "product":
            continue
        spec, size = read_blob(head, path)
        if evidence:
            evidence_bytes += size
            evidence_files += 1
        if path in allowed:
            continue
        if kind == "raw":
            problems.append((path, "raw/generated output belongs in an artifact outside Git"))
        elif kind == "receipt":
            problem = check_receipt(spec, size)
            if problem:
                problems.append((path, problem))
    if evidence_files > MAX_FILES or evidence_bytes > MAX_BYTES:
        problems.append(("evidence budget", "{} files / {} bytes; maximum {} files / {} bytes".format(
            evidence_files, evidence_bytes, MAX_FILES, MAX_BYTES)))
    for path, reason in problems[:30]:
        # Escape control bytes; filenames cannot inject workflow commands.
        print("FAIL {}: {}".format(json.dumps(path, ensure_ascii=True), reason))
    if len(problems) > 30:
        print("FAIL: {} further paths omitted".format(len(problems) - 30))
    print("Generated evidence: {} changed files checked; {} evidence files / {} bytes; {} problem(s).".format(
        len(paths), evidence_files, evidence_bytes, len(problems)))
    if problems:
        print("Link the CI summary and artifacts in the PR; no separate report or receipt is required. "
              "Keep raw output outside Git; compression and force-add do not exempt it.")
    return bool(problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--direct", action="store_true", help="compare the two exact commits, without merge-base")
    args = parser.parse_args()
    base, head = revision(args.base), revision(args.head)
    if not args.direct:
        base = git("merge-base", base, head).decode().strip()
    return int(check(base, head))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (subprocess.CalledProcessError, ValueError, OSError) as error:
        # Never echo raw subprocess output: the repository may contain secrets.
        print("Generated evidence check failed: {}".format(type(error).__name__), file=sys.stderr)
        sys.exit(2)
