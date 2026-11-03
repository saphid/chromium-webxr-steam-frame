#!/bin/bash
# Helpers for .github/workflows/build.yml.
#
# The build takes longer than a GitHub-hosted job may run (6 h), so each job
# builds for about 5 h, then packs the whole tree and hands it to the next job
# as an artifact. The idea comes from ungoogled-chromium-portablelinux.
#
#   ci.sh setup               free disk space, pick CHROMIUM_XR_DIR
#   ci.sh fetch               download the previous job's tree
#   ci.sh restore             unpack it
#   ci.sh build FIRST LAST    build until done or out of time; sets the
#                             step output status=running|completed
#   ci.sh save                pack the tree for the next job
set -euo pipefail

REPO=$(cd "$(dirname "$0")/../.." && pwd)
# On the root disk, so it doesn't take space from the tree on /mnt.
CACHE_DIR=$RUNNER_TEMP/build-tree
CACHE=$CACHE_DIR/build-tree.tar.zst
# Stop building this long after the job starts, leaving time to save the tree.
DEADLINE=$((5 * 3600 + 15 * 60))

case $1 in
  setup)
    echo "JOB_START=$(date +%s)" >> "$GITHUB_ENV"
    # Preinstalled SDKs the build doesn't use; removing them frees about 30 GB.
    sudo rm -rf /usr/local/lib/android /usr/local/.ghcup /usr/lib/jvm \
      /usr/lib/google-cloud-sdk /usr/lib/dotnet /usr/share/swift \
      /opt/hostedtoolcache /usr/local/share/powershell /usr/local/share/chromium
    # The runner's second disk has the most free space, when there is one.
    if mountpoint -q /mnt; then dir=/mnt/chromium-xr; else dir=$HOME/chromium-xr; fi
    sudo mkdir -p "$dir"
    sudo chown "$(id -u):$(id -g)" "$dir"
    echo "CHROMIUM_XR_DIR=$dir" >> "$GITHUB_ENV"
    df -h / "$dir"
    ;;

  fetch)
    # actions/download-artifact fetches the 9 GB tree in one go and starts
    # again from zero after an error. The artifact store sometimes answers
    # 503 to about one request in four for hours, so that never finished
    # (run 39879394713). Resume after each error instead, then check the
    # digest. Needs GH_TOKEN with actions: read.
    mkdir -p "$CACHE_DIR"
    read -r id size digest < <(gh api \
      "repos/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID/artifacts?name=build-tree.tar.zst" \
      -q '.artifacts | max_by(.created_at) | "\(.id) \(.size_in_bytes) \(.digest)"')
    [ -n "$id" ] || { echo "::error::no build-tree.tar.zst artifact in this run"; exit 1; }
    echo "artifact $id, $size bytes"
    for attempt in $(seq 1 300); do
      have=$(stat -c %s "$CACHE" 2>/dev/null || echo 0)
      [ "$have" -lt "$size" ] || break
      # The signed storage URL expires, so ask for a fresh one each time.
      url=$(curl -sS -o /dev/null -w '%{redirect_url}' -H "Authorization: Bearer $GH_TOKEN" \
        "https://api.github.com/repos/$GITHUB_REPOSITORY/actions/artifacts/$id/zip") || url=
      if [ -n "$url" ]; then
        # No --retry: curl's retries restart from where this attempt began,
        # not from where it stopped. The loop resumes instead, and the speed
        # limit turns a stalled connection into an error that it resumes.
        curl -fsS --speed-limit 1000000 --speed-time 60 -C - -o "$CACHE" "$url" ||
          echo "attempt $attempt stopped at $(stat -c %s "$CACHE" 2>/dev/null || echo 0) of $size bytes"
      fi
      sleep 2
    done
    [ "$(stat -c %s "$CACHE" 2>/dev/null || echo 0)" = "$size" ] ||
      { echo "::error::build tree download incomplete"; exit 1; }
    echo "${digest#sha256:}  $CACHE" | sha256sum -c -
    ;;

  restore)
    tree=$(find "$CACHE_DIR" -name '*.tar.zst' | head -n 1)
    zstd -d -c "$tree" | tar -xf - -C "$CHROMIUM_XR_DIR"
    rm -rf "$CACHE_DIR"
    df -h "$CHROMIUM_XR_DIR"
    ;;

  build)
    first=$2 last=$3
    if [ "$first" = true ]; then
      CHROMIUM_XR_STEPS=prepare "$REPO/build/build.sh"
      # Not needed to compile, and a large share of the tree to pass on.
      find "$CHROMIUM_XR_DIR/src" -name .git -prune -exec rm -rf {} +
    fi
    rc=0
    CHROMIUM_XR_STEPS=build BUILD_TIMEOUT=$((JOB_START + DEADLINE - $(date +%s))) \
      "$REPO/build/build.sh" || rc=$?
    if [ "$rc" = 124 ] && [ "$last" != true ]; then
      echo "status=running" >> "$GITHUB_OUTPUT"
      exit 0
    fi
    [ "$rc" = 0 ] || exit "$rc"
    CHROMIUM_XR_STEPS=package "$REPO/build/build.sh"
    echo "status=completed" >> "$GITHUB_OUTPUT"
    ;;

  save)
    mkdir -p "$CACHE_DIR"
    # POSIX (pax) format keeps file times to the nanosecond, so the next part
    # sees exactly the times this one built with; GNU tar's default format
    # rounds them to whole seconds.
    tar --format=posix -cf - -C "$CHROMIUM_XR_DIR" . | zstd -T0 -3 -f -o "$CACHE"
    ls -la "$CACHE"
    ;;

  *)
    echo "usage: $0 setup|restore|build FIRST LAST|save" >&2
    exit 2
    ;;
esac
