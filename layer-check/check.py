#!/usr/bin/env python3
"""Fail when a crate-internal Rust module reference points up a declared layer order.

Each checked crate keeps a `layers.toml` next to its Cargo.toml listing `[[layer]]`
entries bottom-first (`name`, `doc`, `modules`), plus optional top-level `src` and
`exclude` string arrays. Module paths use `::` below `crate` (`crate` owns `lib.rs`).
"""

import argparse
from collections import Counter, defaultdict
import os
import re
import sys

IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
ITEM_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:(?:unsafe|async|const|default)\s+|extern\s+\"[^\"]*\"\s+)*"
    r"(struct|enum|fn|trait|type|const|static|union|mod)\s+(" + IDENT + r")",
    re.M,
)
MACRO_RE = re.compile(r"^\s*macro_rules!\s*(" + IDENT + r")", re.M)
USE_RE = re.compile(r"(?:^|[;{}\s])((?:pub(?:\([^)]*\))?\s+)?)use\s+([^;]+);", re.S)
INLINE_RE = re.compile(r"\b((?:crate|super|self)(?:::(?:super|" + IDENT + r"))+)")
BARE_RE = re.compile(r"(?<![:\w])([a-z_][a-z0-9_]*)((?:::[A-Za-z_][A-Za-z0-9_]*)+)")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
STR_RE = re.compile(r'"([^"\\]*)"')


class LayerFileError(Exception):
    pass


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return re.sub(r"pub\s*\(\s*in\s+[^)]*\)", "pub", text)


def split_top(body):
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p for p in parts if p]


def expand_use(tree):
    tree = re.sub(r"\s+as\s+(" + IDENT + r")", r" as \1", tree)
    out = []

    def rec(prefix, t):
        t = t.strip()
        alias = None
        m = re.match(r"^(.*?)\s+as\s+(" + IDENT + r")$", t, re.S)
        if m and "{" not in m.group(1):
            t, alias = m.group(1), m.group(2)
        t = re.sub(r"\s+", "", t)
        i = t.find("{")
        if i == -1:
            segs = [s for s in (prefix + t).split("::") if s]
            if segs and segs[-1] == "self":
                segs = segs[:-1]
            out.append((segs, alias))
            return
        depth, j = 0, i
        for j in range(i, len(t)):
            if t[j] == "{":
                depth += 1
            elif t[j] == "}":
                depth -= 1
                if depth == 0:
                    break
        for part in split_top(t[i + 1 : j]):
            rec(prefix + t[:i], part)

    rec("", tree)
    return out


def module_of(rel):
    parts = rel[:-3].split("/")
    if parts[-1] in ("mod", "lib", "main"):
        parts = parts[:-1]
    return tuple(parts)


def excluded(rel, excludes):
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in excludes)


class Crate:
    def __init__(self, src, excludes=()):
        self.src = src
        self.files = {}
        self.lines = {}
        self.modules = {}
        self.items = defaultdict(set)
        self.reexports = defaultdict(dict)
        self.globs = defaultdict(list)
        for root, dirs, names in os.walk(src):
            dirs[:] = sorted(d for d in dirs if d not in ("target", ".git"))
            for n in sorted(names):
                if n.endswith(".rs"):
                    full = os.path.join(root, n)
                    rel = os.path.relpath(full, src)
                    if excluded(rel, excludes):
                        continue
                    with open(full, encoding="utf-8", errors="replace") as fh:
                        raw = fh.read()
                    self.lines[rel] = raw.count("\n") + 1
                    self.files[rel] = strip_comments(raw)
                    self.modules[module_of(rel)] = rel
        for rel, text in self.files.items():
            mod = module_of(rel)
            for _kind, name in ITEM_RE.findall(text):
                self.items[mod].add(name)
            for name in MACRO_RE.findall(text):
                self.items[mod].add(name)
        for rel, text in self.files.items():
            mod = module_of(rel)
            for vis, tree in USE_RE.findall(text):
                if not vis.strip():
                    continue
                for segs, alias in expand_use(tree):
                    absp = self.absolute(mod, segs)
                    if absp is None:
                        continue
                    if segs and segs[-1] == "*":
                        self.globs[mod].append(tuple(absp[:-1]))
                    elif absp:
                        self.reexports[mod][alias or absp[-1]] = tuple(absp)

    def absolute(self, mod, segs):
        if not segs:
            return None
        head = segs[0]
        if head == "crate":
            return list(segs[1:])
        if head in ("self", "super"):
            base, rest = list(mod), list(segs)
            if rest[0] == "self":
                rest = rest[1:]
            while rest and rest[0] == "super":
                base, rest = base[:-1], rest[1:]
            return base + rest
        child = tuple(mod) + (head,)
        if child in self.modules:
            return list(child) + list(segs[1:])
        return None

    def module_aliases(self, rel):
        mod = module_of(rel)
        out = {}
        for _, tree in USE_RE.findall(self.files[rel]):
            for segs, alias in expand_use(tree):
                absp = self.absolute(mod, segs)
                if absp and tuple(absp) in self.modules:
                    out[alias or absp[-1]] = tuple(absp)
        return out

    def resolve(self, path, depth=0):
        path = tuple(p for p in path if p != "*")
        cur = ()
        for seg in path:
            if cur + (seg,) in self.modules:
                cur = cur + (seg,)
            else:
                break
        rest = path[len(cur) :]
        if cur not in self.modules:
            return None
        if not rest:
            return self.modules[cur]
        name = rest[0]
        if name in self.items[cur]:
            return self.modules[cur]
        if depth < 8 and name in self.reexports[cur]:
            hit = self.resolve(self.reexports[cur][name] + rest[1:], depth + 1)
            if hit:
                return hit
        if depth < 8:
            for g in self.globs[cur]:
                if name in self.items.get(g, ()) or name in self.reexports.get(g, {}):
                    hit = self.resolve(g + rest, depth + 1)
                    if hit:
                        return hit
        under = [m for m in self.modules if m[: len(cur)] == cur and name in self.items[m]]
        return self.modules[under[0]] if len(under) == 1 else self.modules[cur]

    def references(self, rel):
        mod = module_of(rel)
        text = self.files[rel]
        for _, tree in USE_RE.findall(text):
            for segs, _alias in expand_use(tree):
                absp = self.absolute(mod, segs)
                if absp:
                    hit = self.resolve(absp)
                    if hit:
                        yield hit, "::".join(absp[-2:])
        body = USE_RE.sub(" ", text)
        for m in INLINE_RE.finditer(body):
            segs = m.group(1).split("::")
            absp = self.absolute(mod, segs)
            if absp:
                hit = self.resolve(absp)
                if hit:
                    yield hit, "::".join(absp[-2:])
        aliases = self.module_aliases(rel)
        for m in BARE_RE.finditer(INLINE_RE.sub(" ", body)):
            head = m.group(1)
            rest = [s for s in m.group(2).split("::") if s]
            if head in aliases:
                absp = list(aliases[head]) + rest
            elif tuple(mod) + (head,) in self.modules:
                absp = list(mod) + [head] + rest
            else:
                continue
            hit = self.resolve(tuple(absp))
            if hit:
                yield hit, "::".join(absp[-2:])


def strip_toml_comment(line):
    out, in_str = [], False
    for ch in line:
        if ch == '"':
            in_str = not in_str
        if ch == "#" and not in_str:
            break
        out.append(ch)
    return "".join(out).strip()


def parse_layer_file(path):
    top, layers = {}, []
    cur = top
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        line = strip_toml_comment(raw)
        if not line:
            continue
        if line == "[[layer]]":
            cur = {}
            layers.append(cur)
            continue
        m = KEY_RE.match(line)
        if not m:
            raise LayerFileError(f"{path}:{i}: cannot parse line: {raw}")
        key, value = m.group(1), m.group(2).strip()
        if value.startswith("["):
            buf = value
            while "]" not in STR_RE.sub('""', buf):
                if i >= len(lines):
                    raise LayerFileError(f"{path}:{i}: unclosed array for {key}")
                buf += " " + strip_toml_comment(lines[i])
                i += 1
            cur[key] = STR_RE.findall(buf)
        elif value.startswith('"'):
            sm = STR_RE.fullmatch(value)
            if not sm:
                raise LayerFileError(f"{path}:{i}: bad string for {key}")
            cur[key] = sm.group(1)
        else:
            raise LayerFileError(f"{path}:{i}: only strings and string arrays are allowed: {raw}")
    return top, layers


def module_key(path):
    return () if path == "crate" else tuple(path.split("::"))


def check_crate(crate_dir, layer_file, summary, top):
    meta, layers = parse_layer_file(layer_file)
    src = os.path.join(crate_dir, meta.get("src", "src"))
    crate = Crate(src, meta.get("exclude", []))
    errors, owner, names = [], {}, set()
    for idx, layer in enumerate(layers):
        name = layer.get("name")
        if not name or name in names:
            errors.append(f"layer {idx}: missing or duplicate name {name!r}")
        names.add(name)
        if not layer.get("doc"):
            errors.append(f"layer {name}: missing doc")
        for mod in layer.get("modules", []):
            key = module_key(mod)
            if key in owner:
                errors.append(f"module {mod} is listed in two layers")
            owner[key] = idx
            if (key == () and () not in crate.modules) or (
                key != () and not any(m[: len(key)] == key for m in crate.modules)
            ):
                errors.append(f"module {mod} (layer {name}) does not exist in {src}")

    def layer_of(rel):
        mod = module_of(rel)
        if not mod:
            return owner.get(())
        for n in range(len(mod), 0, -1):
            if mod[:n] in owner:
                return owner[mod[:n]]
        return None

    file_layer = {}
    for rel in sorted(crate.files):
        idx = layer_of(rel)
        if idx is None:
            errors.append(f"unassigned file {rel}: add its module to a layer")
        else:
            file_layer[rel] = idx

    upward = []
    for rel in sorted(file_layer):
        a = file_layer[rel]
        seen = set()
        for target, item in crate.references(rel):
            if target == rel or target not in file_layer:
                continue
            b = file_layer[target]
            if b > a:
                key = (rel, target, item.split("::")[-1])
                if key not in seen:
                    seen.add(key)
                    upward.append((a, b) + key)

    label = os.path.relpath(layer_file)
    if summary:
        lines, files = Counter(), Counter()
        for rel, idx in file_layer.items():
            lines[idx] += crate.lines[rel]
            files[idx] += 1
        print(f"## {label}: {len(layers)} layers, {len(file_layer)} files (bottom first)")
        for idx, layer in enumerate(layers):
            print(f"  {idx:>2} {layer.get('name', '?'):<22} files={files[idx]:<5} lines={lines[idx]}")
    if errors:
        print(f"layer-check: {label}: layer file errors")
        for e in errors:
            print(f"  - {e}")
    if upward:
        by_pair = defaultdict(list)
        for a, b, rel, target, item in upward:
            by_pair[(a, b)].append((rel, target, item))
        print(f"layer-check: {label}: {len(upward)} upward reference(s)")
        for (a, b), refs in sorted(by_pair.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"  {layers[a]['name']} -> {layers[b]['name']}: {len(refs)}")
            for rel, target, item in refs[:top]:
                print(f"    {rel} -> {target} :: {item}")
            if len(refs) > top:
                print(f"    ... {len(refs) - top} more")
    if not errors and not upward:
        print(f"layer-check: {label}: ok ({len(layers)} layers, {len(file_layer)} files)")
    return len(errors) + len(upward)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--crate", action="append", required=True, help="crate directory holding layers.toml")
    ap.add_argument("--layers", default="layers.toml", help="layer file name inside each crate directory")
    ap.add_argument("--summary", action="store_true", help="print files and lines per layer")
    ap.add_argument("--top", type=int, default=1000, help="upward references to print per layer pair")
    args = ap.parse_args()
    failures = 0
    for crate_dir in args.crate:
        layer_file = os.path.join(crate_dir, args.layers)
        try:
            failures += check_crate(crate_dir, layer_file, args.summary, args.top)
        except (OSError, LayerFileError) as exc:
            print(f"layer-check: {exc}")
            failures += 1
    if failures:
        print("Move the referenced item down to the lowest layer that uses it, move the caller up,")
        print("or invert the call with a narrow trait in the lower layer.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
