"""Persistent run state for the local agent runtime."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .stages import STAGE_PENDING, WORKFLOW_STAGES

RUN_PENDING = "pending"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_BLOCKED = "blocked"
RUN_FAILED = "failed"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid4().hex[:8]}"


@dataclass(frozen=True)
class RunPaths:
    runs_dir: Path
    run_dir: Path
    state_path: Path


def paths_for_run(runs_dir: Path, run_id: str) -> RunPaths:
    run_dir = runs_dir / run_id
    return RunPaths(runs_dir=runs_dir, run_dir=run_dir, state_path=run_dir / "state.json")


def initial_state(run_id: str, subject: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "subject": subject,
        "status": RUN_PENDING,
        "current_stage": WORKFLOW_STAGES[0].name,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "stages": {
            stage.name: {
                "status": STAGE_PENDING,
                "artifact": stage.artifact,
                "message": "",
                "started_at": None,
                "finished_at": None,
            }
            for stage in WORKFLOW_STAGES
        },
    }


def read_state(state_path: Path) -> dict[str, Any]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def write_state(state_path: Path, state: dict[str, Any]) -> None:
    state = deepcopy(state)
    state["updated_at"] = utc_now()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
