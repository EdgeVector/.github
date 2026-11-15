#!/usr/bin/env python3
"""Fail a PR that adds more `clippy::too_many_arguments` allows than it removes.

Override one added line with `lint:allow-ok <reason>` on that line or the line above.
"""

import argparse
import json
import re
import subprocess
import sys

OVERRIDE = "lint:allow-ok"
LINT = "clippy::too_many_arguments"
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def silences_lint(text):
    return LINT in text and not text.lstrip().startswith("//")


def git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"lint-diff-new-allows: git {args[0]} failed (exit {out.returncode})")
    return out.stdout


def scan(diff, head):
    added, removed = [], 0
    path, new_no = None, 0
    cache = {}
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            continue
        if line.startswith("--- "):
            continue
        m = HUNK.match(line)
        if m:
            new_no = int(m.group(1))
            continue
        if path is None or not path.endswith(".rs"):
            continue
        if line.startswith("+"):
            if silences_lint(line[1:]):
                if path not in cache:
                    cache[path] = git("show", f"{head}:{path}").splitlines()
                lines = cache[path]
                prev = lines[new_no - 2] if new_no >= 2 else ""
                if OVERRIDE not in line and OVERRIDE not in prev:
                    added.append((path, new_no, line[1:].strip()))
            new_no += 1
        elif line.startswith("-") and silences_lint(line[1:]):
            removed += 1
    return added, removed


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    args = ap.parse_args()

    head = git("rev-parse", "--verify", f"{args.head}^{{commit}}").strip()
    base = git("merge-base", args.base, head).strip()
    diff = git("diff", "-U0", "-M", "--no-color", base, head, "--", "*.rs")
    added, removed = scan(diff, head)
    if len(added) - removed <= 0:
        print(f"allow check passed: {len(added)} added, {removed} removed")
        return 0
    print(
        f"allow check failed: this PR adds {len(added)} `too_many_arguments` allow(s) and removes {removed}.",
        file=sys.stderr,
    )
    for path, no, text in added:
        print(f"  {json.dumps(path, ensure_ascii=True)}:{no}: {text}", file=sys.stderr)
    print(
        f"Group shared values into a context struct instead of silencing clippy, or override with `{OVERRIDE} <reason>`.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
