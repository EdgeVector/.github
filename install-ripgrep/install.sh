#!/usr/bin/env bash
# Install ripgrep 14.1.0 without apt, verified by SHA-256.
set -euo pipefail

if command -v rg >/dev/null 2>&1; then
  echo "ripgrep already on PATH: $(command -v rg)"
  rg --version | head -n 1
  exit 0
fi

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "install-ripgrep: pinned binary is Linux x86_64 only (have $(uname -s) $(uname -m))" >&2
  exit 1
fi

if [[ -z "${GITHUB_PATH:-}" ]]; then
  echo "install-ripgrep: GITHUB_PATH is unset" >&2
  exit 1
fi

version=14.1.0
name="ripgrep-${version}-x86_64-unknown-linux-musl"
expect="f84757b07f425fe5cf11d87df6644691c644a5cd2348a2c670894272999d3ba7"
url="https://github.com/BurntSushi/ripgrep/releases/download/${version}/${name}.tar.gz"
asset_url="https://api.github.com/repos/BurntSushi/ripgrep/releases/assets/144124496"

dest="${RUNNER_TEMP:-/tmp}/ripgrep-${version}"
mkdir -p "$dest"
archive="$dest/${name}.tar.gz"
if ! curl -fsSL --retry 1 --retry-delay 2 -o "$archive" "$url"; then
  curl -fsSL --retry 2 --retry-delay 2 -H 'Accept: application/octet-stream' -o "$archive" "$asset_url"
fi
printf '%s  %s\n' "$expect" "$archive" | sha256sum -c -
tar -xzf "$archive" -C "$dest" "${name}/rg"

bindir="$dest/bin"
mkdir -p "$bindir"
mv "$dest/${name}/rg" "$bindir/rg"
chmod 755 "$bindir/rg"
printf '%s\n' "$bindir" >>"$GITHUB_PATH"
"$bindir/rg" --version
