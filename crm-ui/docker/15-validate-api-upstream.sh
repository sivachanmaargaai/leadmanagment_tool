#!/bin/sh
set -eu
case "${API_UPSTREAM_HOST:-}" in
  ""|*[!a-zA-Z0-9.-]*|.*|-*)
    echo "Set API_UPSTREAM_HOST to the public Render backend hostname (without https:// or a path)." >&2
    exit 1
    ;;
esac
