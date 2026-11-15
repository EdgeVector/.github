#!/usr/bin/env python3
"""Fail a PR that makes a source file too long. Only changed files count.

Override one file with a line containing `lint:file-size-ok <reason>`.
"""

import argparse
import json
import subprocess
import sys

OVERRIDE = "lint:file-size-ok"


def git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"lint-diff-file-size: git {args[0]} failed (exit {out.returncode})")
    return out.stdout


def line_count(text):
    return text.count("\n") + (0 if text.endswith("\n") or not text else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base", required=True, help="base commit")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--max", type=int, default=400, help="limit for source files")
    ap.add_argument("--allow", type=int, default=10, help="lines an already-too-long file may grow")
    ap.add_argument("--ext", action="append", default=None, help="extension, repeatable (default .rs)")
    args = ap.parse_args()
    exts = tuple(args.ext or [".rs"])
    head = git("rev-parse", "--verify", f"{args.head}^{{commit}}").strip()
    base = git("merge-base", args.base, head).strip()

    rows = git("diff", "-M", "--name-status", "--diff-filter=AMR", base, head).splitlines()
    failures = []
    for row in rows:
        status, *paths = row.split("\t")
        status, path, old_path = status[0], paths[-1], paths[0]
        if not path.endswith(exts):
            continue
        new = git("show", f"{head}:{path}")
        if OVERRIDE in new:
            continue
        limit = args.max
        after = line_count(new)
        if after <= limit:
            continue
        safe = json.dumps(path, ensure_ascii=True)
        if status == "A":
            failures.append(f"{safe}: new file has {after} lines, limit {limit}")
            continue
        before = line_count(git("show", f"{base}:{old_path}"))
        if before <= limit:
            failures.append(f"{safe}: grew {before} -> {after} lines, crossed limit {limit}")
        elif after - before > args.allow:
            failures.append(
                f"{safe}: grew {before} -> {after} lines (+{after - before}, allowed +{args.allow}), limit {limit}"
            )

    if failures:
        print("File size check failed (changed files only):")
        for f in failures:
            print(f"  - {f}")
        print("Split the file, or add a line with `lint:file-size-ok <reason>`.")
        return 1
    print(f"File size check passed ({len(rows)} changed file(s) examined).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
