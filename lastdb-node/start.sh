#!/usr/bin/env bash
# Start the newest LastDB nightly on a fresh empty home (Tom, 2026-11-03: app CI
# always runs against the latest nightly, never a pinned one). The node holds
# generated data only. It runs until the job ends; a caller that wants a clean
# stop sends SIGTERM to the pid output.
set -euo pipefail

asset=lastdb-x86_64-unknown-linux-gnu
if [ "$(uname -s)-$(uname -m)" != "Linux-x86_64" ]; then
  echo "lastdb-node: the nightly is fetched for Linux x86_64 only" >&2
  exit 1
fi
case "$START_SECONDS" in
  '' | *[!0-9]*) echo "lastdb-node: start-seconds must be a whole number" >&2; exit 1 ;;
esac

root="$RUNNER_TEMP/lastdb-node"
mkdir "$root" "$root/bin"
mkdir -m 700 "$root/home"

tag="$(gh release list -R EdgeVector/lastdb --exclude-drafts --limit 30 \
  --json tagName,publishedAt \
  --jq '[.[] | select(.tagName | startswith("nightly-"))] | sort_by(.publishedAt) | last | .tagName')"
if [ -z "$tag" ] || [ "$tag" = null ]; then
  echo "lastdb-node: no nightly release of EdgeVector/lastdb was found" >&2
  exit 1
fi
gh release download "$tag" -R EdgeVector/lastdb -D "$root/bin" \
  -p "$asset.tar.gz" -p "$asset.manifest.json" -p SHA256SUMS.txt
(cd "$root/bin" && grep " $asset.tar.gz\$" SHA256SUMS.txt | sha256sum --check --status)
tar -xzf "$root/bin/$asset.tar.gz" -C "$root/bin"
manifest="$root/bin/$asset.manifest.json"
want="$(jq -r '.binaries[] | select(.name == "lastdbd") | .sha256' "$manifest")"
have="$(sha256sum "$root/bin/lastdbd" | cut -d' ' -f1)"
if [ -z "$want" ] || [ "$want" != "$have" ]; then
  echo "lastdb-node: lastdbd does not match the nightly manifest" >&2
  exit 1
fi
revision="$(jq -r .source_git_oid "$manifest")"

socket="$root/q.sock"
log="$root/node.log"
# LASTDB_ISOLATED_COPY lets a job declare its own schemas on this generated home.
LASTDB_ISOLATED_COPY=1 LASTDB_SUPPRESS_RECOVERY_PHRASE=1 LASTDB_HOME="$root/home" \
  ENVIRONMENT=dev RUST_MIN_STACK=16777216 \
  nohup "$root/bin/lastdbd" --data-dir "$root/home" --socket-path "$socket" \
  > "$log" 2>&1 < /dev/null &
pid=$!
disown "$pid"

deadline=$((SECONDS + START_SECONDS))
healthy=0
while [ "$SECONDS" -lt "$deadline" ]; do
  if ! kill -0 "$pid" 2> /dev/null; then
    echo "lastdb-node: the node exited before it reported health" >&2
    tail -n 40 "$log" >&2
    exit 1
  fi
  if [ -S "$socket" ] && curl --silent --fail --max-time 5 --unix-socket "$socket" \
    http://localhost/health 2> /dev/null | jq -e '.status == "ok"' > /dev/null; then
    healthy=1
    break
  fi
  sleep 0.2
done
if [ "$healthy" != 1 ]; then
  echo "lastdb-node: the node did not report health in $START_SECONDS seconds" >&2
  tail -n 40 "$log" >&2
  exit 1
fi

version="$(curl --silent --fail --max-time 5 --unix-socket "$socket" http://localhost/api/version)"
api="$(jq -r .api_version <<< "$version")"
build="$(jq -r .build <<< "$version")"
format="unreported"
if [ -f "$root/home/data/laststore-pack-node-v1" ]; then
  format="$(tr -d '\n' < "$root/home/data/laststore-pack-node-v1" | cut -c1-80)"
fi

{
  printf 'socket=%s\nhome=%s\nlog=%s\npid=%s\nbin=%s\n' "$socket" "$root/home" "$log" "$pid" "$root/bin"
  printf 'tag=%s\nrevision=%s\napi-version=%s\n' "$tag" "$revision" "$api"
} >> "$GITHUB_OUTPUT"
printf 'LASTDB_SOCKET_PATH=%s\n' "$socket" >> "$GITHUB_ENV"
printf 'LastDB node: %s at %s, lastdbd SHA-256 %s, build %s, API %s, home marker %s\n' \
  "$tag" "$revision" "$have" "$build" "$api" "$format" | tee -a "$GITHUB_STEP_SUMMARY"
