"""TraceWriter: persists per-agent JSON dumps and a top-level trace.json."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class TraceWriter:
    """Writes intermediate/<NN>_<agent>.json files and a final trace.json.

    When `run_dir` is None, all methods are no-ops. This lets tests pass
    `TraceWriter(run_dir=None)` to disable trace writing.
    """

    def __init__(self, run_dir: Path | None) -> None:
        self.run_dir = run_dir
        self.steps: list[dict[str, Any]] = []
        self.costs: list[float] = []
        self._started_at = time.time()
        if run_dir is not None:
            (run_dir / "intermediate").mkdir(parents=True, exist_ok=True)

    def write_step(self, agent: str, data: dict[str, Any]) -> None:
        idx = len(self.steps)
        payload = {
            "step": idx,
            "agent": agent,
            "elapsed_s": round(time.time() - self._started_at, 3),
            "data": data,
        }
        self.steps.append(payload)
        if self.run_dir is None:
            return
        out = self.run_dir / "intermediate" / f"{idx:02d}_{agent}.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def add_cost(self, usd: float) -> None:
        self.costs.append(usd)

    def finalize(self) -> Path | None:
        if self.run_dir is None:
            return None
        out = self.run_dir / "trace.json"
        out.write_text(
            json.dumps(
                {
                    "total_cost_usd": round(sum(self.costs), 4),
                    "total_elapsed_s": round(time.time() - self._started_at, 3),
                    "steps": self.steps,
                },
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )
        return out
