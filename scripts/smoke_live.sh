#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
gh auth status
tmp_root="$(mktemp -d)"
echo "Live smoke output retained at: $tmp_root"
sed "s|../../runs/consul|$tmp_root/run|" \
  "$project_root/examples/configs/single-project.yml" > "$tmp_root/config.yml"
uv run --project "$project_root" gobugminer mine --config "$tmp_root/config.yml"
uv run --project "$project_root" gobugminer validate "$tmp_root/run"
