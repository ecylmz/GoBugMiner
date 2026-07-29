from __future__ import annotations

import csv
from pathlib import Path

import pytest

from gobugminer.exceptions import ValidationError
from gobugminer.validation.run import validate


def test_missing_run_files(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="missing file"):
        validate(tmp_path)


def test_relation_duplicate_and_integrity(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    from gobugminer.config import load_config
    from gobugminer.outputs.writer import checksums
    from gobugminer.pipeline import mine

    config, _repo, _fix, _bic = offline_case
    output = mine(load_config(config), offline=True)
    relation = output / "normalized/fix_bic_relations.csv"
    with relation.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    with relation.open("a", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=fields).writerow(rows[0])
    checksums(output)
    with pytest.raises(ValidationError, match="duplicate"):
        validate(output)


def test_missing_required_checksum_entry_fails(
    offline_case: tuple[Path, Path, str, str],
) -> None:
    from gobugminer.config import load_config
    from gobugminer.pipeline import mine

    config, _repo, _fix, _bic = offline_case
    output = mine(load_config(config), offline=True)
    checksum_path = output / "provenance/checksums.sha256"
    lines = checksum_path.read_text(encoding="utf-8").splitlines()
    checksum_path.write_text(
        "\n".join(line for line in lines if not line.endswith("metrics/commits.csv")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match=r"missing checksum entry: metrics/commits\.csv"):
        validate(output)
