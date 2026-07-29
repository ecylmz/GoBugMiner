# GoBugMiner

GoBugMiner is an open-source command-line tool for constructing
multi-granularity defect datasets from public Go repositories.

It discovers bug-labeled merged pull requests, resolves fix revisions,
identifies candidate bug-introducing commits, and extracts commit-, file-, and
method-level metrics with provenance and validation.

> **Status:** v1.0 Software Impacts submission release. Version 1.x supports
> public Go repositories and schema version 1.

## Scientific context

GoBugMiner was used to construct the GoBug dataset reported by Yılmaz and
Oktaş in *IEEE Access*
(https://doi.org/10.1109/ACCESS.2026.3682160).

The study version performed bug-labeled pull-request discovery, fix-revision
resolution, candidate bug-introducing commit identification, production-Go
filtering, and commit-, file-, and method-level metric extraction. Its target
repositories and project-specific bug labels were defined directly in the
source code.

The standalone release preserves this data-collection and metric-extraction
workflow while generalizing project selection through YAML configuration and
command-line options. It also provides package metadata, provenance records,
validation, privacy controls, automated tests, documentation, and
deterministic reproduction infrastructure.

GoBugMiner does not bundle the GoBug dataset, machine-learning experiments,
resampling, tuning, statistical analyses, or publication-specific outputs.

## Features

- Finds closed, labeled GitHub pull requests through the authenticated `gh`
  CLI and resolves merged fix commits.
- Applies PyDriller last-modified-line analysis and reports **candidate**
  bug-introducing commits, never verified bug origins;
- scopes candidate evidence to the configured production-Go source policy by
  default, with an explicit all-changed comparison mode;
- preserves GitHub merge evidence separately from the safely analyzable fix
  revision when merge strategy requires a verified fallback;
- extracts production-Go metrics at commit, file, and method granularity;
- keeps PR evidence, fix/BIC relations, metrics, labels, and provenance
  separate;
- writes canonical CSV/JSON/Markdown outputs with SHA-256 checksums;
- accepts strict single-project or batch YAML and direct CLI overrides;
- records structured JSONL events and hash-chained stage inputs for
  restart-safe execution;
- validates referential integrity and supports a credential-free deterministic
  demonstration.

GoBugMiner does not train models, resample classes, select features, perform
statistical tests, support private repositories, or execute mined project code.

## Requirements and installation

Linux and macOS are supported with Python 3.11 or newer, `git`, `gh`, and
[`uv`](https://docs.astral.sh/uv/). Windows support is not claimed.

```bash
git clone https://github.com/ecylmz/GoBugMiner
cd GoBugMiner
uv sync --all-groups
uv run gobugminer --help
```

For live mining, authenticate once:

```bash
gh auth login
gh auth status
```

## Five-minute offline quick start

The offline demonstration builds a tiny local Git history, uses a frozen PR
response, runs all three metric levels twice, checks deterministic research
outputs, and validates both runs:

```bash
./scripts/reproduce_offline.sh
```

No GitHub credential or target-project code execution is required.

## Live example

The bundled example is intentionally bounded by `max_prs` for demonstration;
that option creates a sample and must not be mistaken for a complete dataset.
The release-pinned `gin-gonic/gin` validation snapshot is retained under
[`examples/paper/`](examples/paper/).

```bash
uv run gobugminer mine --config examples/configs/single-project.yml
uv run gobugminer validate examples/configs/runs/consul
uv run gobugminer inspect examples/configs/runs/consul
```

Create a configuration with:

```bash
uv run gobugminer init --output gobugminer.yml
```

CLI values take precedence over YAML values; YAML values take precedence over
built-in defaults. A direct, configuration-free invocation is also supported:

```bash
uv run gobugminer mine \
  --repo hashicorp/consul \
  --bug-label type/bug \
  --levels commit,file,method \
  --output ./runs/consul
```

See [the CLI reference](docs/cli-reference.md) for all overrides and
[configuration](docs/configuration.md) for batch execution.

## Outputs

Each run separates `raw/`, `normalized/`, `metrics/`, `labels/`, `reports/`,
and `provenance/`. `RUN_COMPLETE` is written only after final checksum,
relationship, label-policy, duplicate-key, and deterministic-order validation
passes. See
[the data model](docs/data-model.md), [metric definitions](docs/metrics.md),
and [provenance guide](docs/provenance.md).

## Limitations

Bug labels are project-specific and do not prove that a PR is a valid bug fix.
GitHub's merge SHA can reflect different merge strategies. SZZ-style blame is
uncertain under refactoring, movement, merges, deletions, and incomplete
history. Parser and Git failures are retained as warnings rather than silently
converted to evidence. Complete-history mining may be expensive. Version 1.x
is Go-only.

## Citation

Use [CITATION.cff](CITATION.cff) for software metadata. Until the Software
Impacts article or an archive DOI exists, cite the exact GitHub release and
version; no DOI is implied.

## Support, contribution, and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
Source code is licensed under Apache License 2.0. The relationship between
GoBugMiner and the peer-reviewed GoBug study is described in the Scientific
context section and in [NOTICE](NOTICE).
