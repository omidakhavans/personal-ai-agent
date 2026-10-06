"""Persistence ports and the Phase 2 filesystem adapters."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .domain import RunSnapshot
from .state import (
    RunPaths,
    paths_for_run,
    read_private_config,
    read_state,
    run_lock,
    write_private_config,
    write_state,
)


@dataclass(frozen=True)
class RunWorkspace:
    """Storage location supplied to stage executors for one workflow run."""

    run_id: str
    run_dir: Path


class RunRepository(Protocol):
    """Durable checkpoint boundary used by application orchestration."""

    def create(self, snapshot: RunSnapshot) -> RunWorkspace:
        """Allocate durable storage for a new run without checkpointing it."""

    def open(self, run_id: str) -> RunWorkspace:
        """Locate an existing run workspace."""

    def lock(self, workspace: RunWorkspace) -> AbstractContextManager[None]:
        """Acquire exclusive advancement access for one workspace."""

    def load(self, workspace: RunWorkspace) -> RunSnapshot:
        """Load a validated workflow checkpoint."""

    def save(self, workspace: RunWorkspace, snapshot: RunSnapshot) -> None:
        """Persist one checkpoint after a transition."""

    def save_private_config(self, workspace: RunWorkspace, config: dict[str, object]) -> None:
        """Persist machine-local resume inputs outside shareable state."""

    def load_private_config(self, workspace: RunWorkspace) -> dict[str, object]:
        """Load machine-local resume inputs for an existing run."""


class ArtifactStore(Protocol):
    """Artifact boundary for workflow checks and deterministic approval output."""

    def write_text(self, workspace: RunWorkspace, name: str, content: str) -> None:
        """Write one named artifact for a run."""

    def validation_error(self, workspace: RunWorkspace, name: str) -> str | None:
        """Return a safe message when an expected artifact is not usable."""


class FileRunRepository:
    """Adapt the existing state-file, lock, and private-config behavior to a port."""

    def __init__(self, runs_dir: Path) -> None:
        """Store the root directory used for file-backed run workspaces."""
        self.runs_dir = runs_dir

    def create(self, snapshot: RunSnapshot) -> RunWorkspace:
        """Create a fresh run directory for a new snapshot."""
        paths = paths_for_run(self.runs_dir, snapshot.run_id)
        paths.run_dir.mkdir(parents=True, exist_ok=False)
        return self._workspace(paths)

    def open(self, run_id: str) -> RunWorkspace:
        """Resolve an existing run ID to its filesystem workspace."""
        return self._workspace(paths_for_run(self.runs_dir, run_id))

    def lock(self, workspace: RunWorkspace) -> AbstractContextManager[None]:
        """Delegate exclusive access to the existing POSIX run lock."""
        return run_lock(workspace.run_dir)

    def load(self, workspace: RunWorkspace) -> RunSnapshot:
        """Read validated JSON state and adapt it into the domain record."""
        return RunSnapshot.from_dict(read_state(workspace.run_dir / "state.json"))

    def save(self, workspace: RunWorkspace, snapshot: RunSnapshot) -> None:
        """Persist the domain record through the existing atomic JSON writer."""
        write_state(workspace.run_dir / "state.json", snapshot.to_dict())

    def save_private_config(self, workspace: RunWorkspace, config: dict[str, object]) -> None:
        """Keep private resume inputs in the existing owner-only config location."""
        write_private_config(self.runs_dir, workspace.run_id, config)

    def load_private_config(self, workspace: RunWorkspace) -> dict[str, object]:
        """Load the private resume config through the existing validation path."""
        return read_private_config(self.runs_dir, workspace.run_id)

    @staticmethod
    def _workspace(paths: RunPaths) -> RunWorkspace:
        """Translate legacy path metadata into the application-facing workspace."""
        return RunWorkspace(run_id=paths.run_dir.name, run_dir=paths.run_dir)


class FileArtifactStore:
    """Constrain named artifacts to the current filesystem workspace."""

    def write_text(self, workspace: RunWorkspace, name: str, content: str) -> None:
        """Write a UTF-8 text artifact after verifying its workspace location."""
        self._path_for(workspace, name).write_text(content, encoding="utf-8")

    def validation_error(self, workspace: RunWorkspace, name: str) -> str | None:
        """Verify that an expected artifact is a non-empty file in this workspace."""
        artifact_path = self._path_for(workspace, name)
        if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
            return "reported success without a readable artifact."
        return None

    @staticmethod
    def _path_for(workspace: RunWorkspace, name: str) -> Path:
        """Reject artifact names that could leave the allocated run workspace."""
        artifact_path = (workspace.run_dir / name).resolve()
        if artifact_path.parent != workspace.run_dir.resolve():
            raise ValueError("Artifact path resolves outside the run workspace.")
        return artifact_path
