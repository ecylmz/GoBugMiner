from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar


class RunLogger:
    """Append machine-readable, token-free events to a run-local JSONL file."""

    LEVELS: ClassVar[dict[str, int]] = {
        "DEBUG": 10,
        "INFO": 20,
        "WARNING": 30,
        "ERROR": 40,
    }

    def __init__(self, root: Path, level: str = "INFO") -> None:
        self.path = root / "logs/events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.threshold = self.LEVELS[level.upper()]

    def emit(
        self,
        level: str,
        event: str,
        message: str,
        *,
        stage: str | None = None,
        **fields: Any,
    ) -> None:
        normalized = level.upper()
        if self.LEVELS[normalized] < self.threshold:
            return
        row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": normalized,
            "event": event,
            "message": message,
            **({"stage": stage} if stage else {}),
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
