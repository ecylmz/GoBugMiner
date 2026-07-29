#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
trap 'rm -rf "$fixture_root"' EXIT
if [[ -n "${GOBUGMINER_WHEEL:-}" ]]; then
  gobugminer=(uv run --isolated --with "$GOBUGMINER_WHEEL" gobugminer)
else
  gobugminer=(uv run --project "$project_root" gobugminer)
fi

repo_path="$fixture_root/repository"
mkdir -p "$repo_path"
git -C "$repo_path" init -b main >/dev/null
git -C "$repo_path" config user.name "GoBugMiner Fixture"
git -C "$repo_path" config user.email "fixture@example.invalid"

export GIT_AUTHOR_DATE="2026-01-01T00:00:00Z"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
cp "$project_root/examples/offline-fixture/initial.go" "$repo_path/calc.go"
git -C "$repo_path" add calc.go
git -C "$repo_path" commit -m "initial implementation" >/dev/null

export GIT_AUTHOR_DATE="2026-01-02T00:00:00Z"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
cp "$project_root/examples/offline-fixture/buggy.go" "$repo_path/calc.go"
git -C "$repo_path" commit -am "introduce arithmetic defect" >/dev/null

export GIT_AUTHOR_DATE="2026-01-03T00:00:00Z"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
cp "$project_root/examples/offline-fixture/calc_test.go" "$repo_path/calc_test.go"
git -C "$repo_path" add calc_test.go
git -C "$repo_path" commit -m "add test fixture" >/dev/null

export GIT_AUTHOR_DATE="2026-01-04T00:00:00Z"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
cp "$project_root/examples/offline-fixture/fixed.go" "$repo_path/calc.go"
printf '\n// Fixed behavior.\n' >> "$repo_path/calc_test.go"
git -C "$repo_path" commit -am "fix arithmetic defect" >/dev/null
fix_sha="$(git -C "$repo_path" rev-parse HEAD)"

sed "s/FIXTURE_FIX_SHA/$fix_sha/g" \
  "$project_root/examples/offline-fixture/pull_requests.template.json" \
  > "$fixture_root/pull_requests.json"

for run_number in 1 2; do
  sed \
    -e "s|FIXTURE_REPOSITORY|$repo_path|g" \
    -e "s|FIXTURE_PULL_REQUESTS|$fixture_root/pull_requests.json|g" \
    -e "s|FIXTURE_OUTPUT|$fixture_root/run-$run_number|g" \
    "$project_root/examples/offline-fixture/config.template.yml" \
    > "$fixture_root/config-$run_number.yml"
  "${gobugminer[@]}" mine \
    --config "$fixture_root/config-$run_number.yml" --offline
  "${gobugminer[@]}" validate "$fixture_root/run-$run_number"
done

for relative in \
  normalized/pull_requests.csv \
  normalized/fix_commits.csv \
  normalized/bic_candidates.csv \
  normalized/fix_bic_relations.csv \
  metrics/commits.csv \
  metrics/files.csv \
  metrics/methods.csv \
  labels/commit_labels.csv \
  labels/file_labels.csv \
  labels/method_labels.csv; do
  cmp "$fixture_root/run-1/$relative" "$fixture_root/run-2/$relative"
done

summary_output="${GOBUGMINER_SUMMARY_OUTPUT:-$project_root/examples/paper/offline-reproduction-summary.json}"
uv run --project "$project_root" python \
  "$project_root/scripts/summarize_offline.py" \
  "$fixture_root/run-1" \
  "$fixture_root/run-2" \
  "$summary_output"

echo "Offline reproduction passed: canonical research outputs are byte-identical."
