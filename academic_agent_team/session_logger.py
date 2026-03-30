from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class SessionLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def tail(self, limit: int = 10) -> Iterable[dict]:
        if not self.log_path.exists():
            return []
        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records
