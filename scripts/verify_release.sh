#!/usr/bin/env bash
set -euo pipefail

version="${1:-v1.0}"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
download_root="$(mktemp -d)"
trap 'rm -rf "$download_root"' EXIT
gh release download "$version" --repo ecylmz/GoBugMiner --dir "$download_root"
sha256sum "$download_root"/*
wheel="$(find "$download_root" -maxdepth 1 -name 'gobugminer-*.whl' -print -quit)"
test -n "$wheel"
uv run --isolated --with "$wheel" gobugminer version
GOBUGMINER_WHEEL="$wheel" \
GOBUGMINER_SUMMARY_OUTPUT="$download_root/offline-reproduction-summary.json" \
  "$project_root/scripts/reproduce_offline.sh"
echo "Release artifacts downloaded, hashed, installed, and reproduced successfully."
