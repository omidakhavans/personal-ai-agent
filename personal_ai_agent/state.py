"""Persistent run state for the local agent runtime."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypeAlias, cast
from uuid import uuid4

from .stages import STAGE_PENDING, STAGE_SKIPPED, WORKFLOW_STAGES, StageStatus

RunStatus: TypeAlias = Literal[
    "pending", "running", "completed", "blocked", "failed", "awaiting_approval"
]

RUN_PENDING: RunStatus = "pending"
RUN_RUNNING: RunStatus = "running"
RUN_COMPLETED: RunStatus = "completed"
RUN_BLOCKED: RunStatus = "blocked"
RUN_FAILED: RunStatus = "failed"
RUN_AWAITING_APPROVAL: RunStatus = "awaiting_approval"
STATE_VERSION = 3
RUN_ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")
RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RUN_PENDING,
        RUN_RUNNING,
        RUN_COMPLETED,
        RUN_BLOCKED,
        RUN_FAILED,
        RUN_AWAITING_APPROVAL,
    }
)
STAGE_STATUSES: frozenset[StageStatus] = frozenset(
    {
        "pending",
        "running",
        "completed",
        "skipped",
        "blocked",
        "failed",
        "awaiting_approval",
    }
)


class StateError(RuntimeError):
    """A persisted run state or run identifier cannot be used safely."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid4().hex[:8]}"


@dataclass(frozen=True)
class RunPaths:
    runs_dir: Path
    run_dir: Path
    state_path: Path


def private_config_path(runs_dir: Path, run_id: str) -> Path:
    """Locate machine-local resume configuration outside shareable run artifacts."""
    paths_for_run(runs_dir, run_id)
    return runs_dir.expanduser().resolve() / ".runtime-config" / f"{run_id}.json"


def paths_for_run(runs_dir: Path, run_id: str) -> RunPaths:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise StateError("Run id is invalid.")
    resolved_runs_dir = runs_dir.expanduser().resolve()
    run_dir = (resolved_runs_dir / run_id).resolve()
    if run_dir.parent != resolved_runs_dir:
        raise StateError("Run id resolves outside the runs directory.")
    return RunPaths(runs_dir=resolved_runs_dir, run_dir=run_dir, state_path=run_dir / "state.json")


def initial_state(
    run_id: str,
    subject: str,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not subject.strip():
        raise StateError("Run subject must not be empty.")
    return {
        "state_version": STATE_VERSION,
        "run_id": run_id,
        "subject": subject,
        "inputs": inputs or {},
        "status": RUN_PENDING,
        "current_stage": WORKFLOW_STAGES[0].name,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "stages": {
            stage.name: {
                "status": STAGE_PENDING,
                "artifact": stage.artifact,
                "message": "",
                "attempts": 0,
                "started_at": None,
                "finished_at": None,
            }
            for stage in WORKFLOW_STAGES
        },
    }


def read_state(state_path: Path) -> dict[str, Any]:
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError("Run state was not found.") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("Run state is unreadable or corrupt.") from exc
    state = _migrate_state(state)
    _validate_state(state)
    return cast(dict[str, Any], state)


def write_state(state_path: Path, state: dict[str, Any]) -> None:
    state = deepcopy(state)
    state["updated_at"] = utc_now()
    _validate_state(state)
    _write_json_atomically(state_path, state)


def write_private_config(runs_dir: Path, run_id: str, config: dict[str, Any]) -> None:
    """Persist local locations needed for resume, without exposing them in artifacts."""
    path = private_config_path(runs_dir, run_id)
    _validate_private_config(config)
    _write_json_atomically(path, config)
    os.chmod(path.parent, 0o700)
    os.chmod(path, 0o600)


def read_private_config(runs_dir: Path, run_id: str) -> dict[str, Any]:
    path = private_config_path(runs_dir, run_id)
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StateError("Local resume configuration was not found; pass all run options explicitly.") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StateError("Local resume configuration is unreadable or corrupt.") from exc
    if not isinstance(config, dict):
        raise StateError("Private run configuration is invalid.")
    _validate_private_config(config)
    return config


def _write_json_atomically(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except OSError as exc:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise StateError("Persistent run data could not be checkpointed.") from exc


@contextmanager
def run_lock(run_dir: Path):
    """Prevent two local CLI processes from advancing the same run concurrently."""
    try:
        import fcntl
    except ImportError as exc:  # pragma: no cover - this local runtime targets POSIX hosts.
        raise StateError("This runtime requires POSIX file locking.") from exc

    if not run_dir.is_dir():
        raise StateError("Run was not found.")
    lock_path = run_dir / ".runtime.lock"
    lock_file = lock_path.open("a+", encoding="utf-8")
    os.chmod(lock_path, 0o600)
    try:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StateError("This run is already being advanced by another process.") from exc
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def _validate_state(state: Any) -> None:
    if not isinstance(state, dict):
        raise StateError("Run state has an invalid format.")
    required = {
        "state_version",
        "run_id",
        "subject",
        "inputs",
        "status",
        "current_stage",
        "created_at",
        "updated_at",
        "stages",
    }
    if not required.issubset(state):
        raise StateError("Run state is missing required fields.")
    if state["state_version"] != STATE_VERSION:
        raise StateError("Run state version is unsupported.")
    if not isinstance(state["run_id"], str) or not RUN_ID_PATTERN.fullmatch(state["run_id"]):
        raise StateError("Run state contains an invalid run id.")
    if not isinstance(state["subject"], str) or not state["subject"].strip():
        raise StateError("Run state has invalid inputs.")
    if not isinstance(state["inputs"], dict):
        raise StateError("Run state has invalid inputs.")
    if state["status"] not in RUN_STATUSES:
        raise StateError("Run state has an invalid run status.")
    stage_names = {stage.name for stage in WORKFLOW_STAGES}
    if state["current_stage"] is not None and state["current_stage"] not in stage_names:
        raise StateError("Run state has an invalid current stage.")
    if not all(isinstance(state[key], str) for key in ("created_at", "updated_at")):
        raise StateError("Run state has invalid timestamps.")
    if not isinstance(state["stages"], dict):
        raise StateError("Run state has invalid stage data.")
    if set(state["stages"]) != stage_names:
        raise StateError("Run state has an unexpected stage set.")
    for stage in WORKFLOW_STAGES:
        stage_state = state["stages"].get(stage.name)
        expected = {"status", "artifact", "message", "attempts", "started_at", "finished_at"}
        if not isinstance(stage_state, dict) or set(stage_state) != expected:
            raise StateError(f"Run state has invalid data for stage {stage.name!r}.")
        if stage_state["status"] not in STAGE_STATUSES:
            raise StateError(f"Run state has invalid data for stage {stage.name!r}.")
        if stage_state["artifact"] != stage.artifact or not isinstance(stage_state["message"], str):
            raise StateError(f"Run state has invalid artifact data for stage {stage.name!r}.")
        if (
            not isinstance(stage_state["attempts"], int)
            or isinstance(stage_state["attempts"], bool)
            or stage_state["attempts"] < 0
        ):
            raise StateError(f"Run state has invalid attempt data for stage {stage.name!r}.")
        if stage_state["started_at"] is not None and not isinstance(stage_state["started_at"], str):
            raise StateError(f"Run state has invalid start time for stage {stage.name!r}.")
        if stage_state["finished_at"] is not None and not isinstance(stage_state["finished_at"], str):
            raise StateError(f"Run state has invalid finish time for stage {stage.name!r}.")


def _validate_private_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get("repository"), str) or not isinstance(config.get("model"), str):
        raise StateError("Private run configuration is invalid.")
    if not isinstance(config.get("resources"), list) or not all(isinstance(item, str) for item in config["resources"]):
        raise StateError("Private run configuration is invalid.")
    options = config.get("model_options")
    if options is not None:
        if not isinstance(options, dict) or set(options) != {
            "timeout_seconds",
            "max_attempts",
            "max_output_tokens",
        }:
            raise StateError("Private model runtime configuration is invalid.")
        for key in ("timeout_seconds", "max_attempts"):
            value = options[key]
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise StateError("Private model runtime configuration is invalid.")
        output_limit = options["max_output_tokens"]
        if output_limit is not None and (
            not isinstance(output_limit, int)
            or isinstance(output_limit, bool)
            or output_limit <= 0
        ):
            raise StateError("Private model runtime configuration is invalid.")


def _migrate_state(state: Any) -> Any:
    """Keep pre-hardening local runs readable while preserving their audit data."""
    if not isinstance(state, dict) or state.get("state_version") not in {None, 1, 2}:
        return state
    migrated = deepcopy(state)
    if migrated.get("state_version") in {None, 1}:
        migrated["state_version"] = 2
        for stage in migrated.get("stages", {}).values():
            if isinstance(stage, dict):
                stage.setdefault("attempts", 0)
    if migrated.get("state_version") == 2:
        stages = migrated.setdefault("stages", {})
        if "approve-social" not in stages:
            later_statuses = [stages.get(name, {}).get("status") for name in ("write-linkedin", "write-x")]
            stages["approve-social"] = {
                "status": STAGE_SKIPPED if migrated.get("status") == RUN_COMPLETED or any(status in {"completed", "skipped"} for status in later_statuses) else STAGE_PENDING,
                "artifact": "approval.md",
                "message": "Legacy run predates the explicit social-approval checkpoint.",
                "attempts": 0,
                "started_at": None,
                "finished_at": None,
            }
        migrated["state_version"] = STATE_VERSION
    return migrated
