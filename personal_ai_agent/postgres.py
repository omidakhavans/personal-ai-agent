"""SQLAlchemy persistence adapter for durable, queryable workflow snapshots.

The domain and orchestration layers only depend on ``RunRepository``.  This
module is an infrastructure adapter: it translates those records into rows and
keeps SQLAlchemy out of the workflow rules.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, cast

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

from .domain import ArtifactReference, RunSnapshot, RunStatus, StageSnapshot
from .persistence import RunWorkspace
from .state import paths_for_run, read_private_config, write_private_config


class Base(DeclarativeBase):
    """Metadata owned by this adapter and used by Alembic migrations."""


class RunRow(Base):
    """Relational representation of one workflow checkpoint."""

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    stages: Mapped[list[RunStageRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class RunStageRow(Base):
    """Relational representation of a single stage's latest checkpoint."""

    __tablename__ = "run_stages"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.run_id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    artifact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run: Mapped[RunRow] = relationship(back_populates="stages")


def create_test_engine() -> Engine:
    """Create an in-memory engine for adapter contract tests only.

    Production configuration must use PostgreSQL and Alembic migrations.  The
    shared SQLite connection lets unit tests exercise the adapter without a
    developer machine database.
    """
    return create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def create_schema_for_tests(engine: Engine) -> None:
    """Create the adapter schema for isolated unit tests, never for deployment."""
    Base.metadata.create_all(engine)


class SqlAlchemyRunRepository:
    """Persist workflow snapshots in PostgreSQL while preserving file artifacts.

    PostgreSQL is the supported deployment target.  An injected SQLite engine
    is accepted solely by the adapter's fast contract test; application code
    should construct this repository from a PostgreSQL URL and run Alembic.
    """

    def __init__(
        self,
        *,
        database_url: str | None = None,
        artifact_root: Path,
        private_config_root: Path | None = None,
        engine: Engine | None = None,
    ) -> None:
        """Set database and local artifact locations without creating schema."""
        if engine is None and not database_url:
            raise ValueError("Provide a PostgreSQL database URL or a test engine.")
        self.engine = engine or create_engine(cast(str, database_url))
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.artifact_root = artifact_root
        self.private_config_root = private_config_root or artifact_root
        self._local_locks: dict[str, RLock] = {}
        self._local_locks_guard = RLock()

    def create(self, snapshot: RunSnapshot) -> RunWorkspace:
        """Allocate the artifact workspace and insert the initial run snapshot."""
        workspace = self._workspace(snapshot.run_id)
        workspace.run_dir.mkdir(parents=True, exist_ok=False)
        with self._sessions.begin() as session:
            session.add(self._row_from_snapshot(snapshot))
        return workspace

    def open(self, run_id: str) -> RunWorkspace:
        """Find an existing database run and return its confined artifact workspace."""
        workspace = self._workspace(run_id)
        with self._sessions() as session:
            if session.get(RunRow, run_id) is None:
                raise ValueError(f"Run {run_id!r} does not exist.")
        return workspace

    def lock(self, workspace: RunWorkspace) -> AbstractContextManager[None]:
        """Serialize advancement with a PostgreSQL advisory lock when available."""
        if self.engine.dialect.name == "postgresql":
            return self._postgres_lock(workspace.run_id)
        return self._local_lock(workspace.run_id)

    def load(self, workspace: RunWorkspace) -> RunSnapshot:
        """Load the latest relational checkpoint into the storage-neutral record."""
        with self._sessions() as session:
            row = session.get(RunRow, workspace.run_id)
            if row is None:
                raise ValueError(f"Run {workspace.run_id!r} does not exist.")
            return self._snapshot_from_row(row)

    def save(self, workspace: RunWorkspace, snapshot: RunSnapshot) -> None:
        """Replace the stored checkpoint fields while retaining the run identity."""
        if workspace.run_id != snapshot.run_id:
            raise ValueError("Workspace and snapshot run IDs must match.")
        with self._sessions.begin() as session:
            row = session.get(RunRow, workspace.run_id)
            if row is None:
                raise ValueError(f"Run {workspace.run_id!r} does not exist.")
            self._apply_snapshot(row, snapshot)

    def save_private_config(self, workspace: RunWorkspace, config: dict[str, object]) -> None:
        """Keep machine-local resume inputs in the owner-only private file store."""
        write_private_config(self.private_config_root, workspace.run_id, config)

    def load_private_config(self, workspace: RunWorkspace) -> dict[str, object]:
        """Load private resume inputs without placing them in relational state."""
        return read_private_config(self.private_config_root, workspace.run_id)

    @contextmanager
    def _postgres_lock(self, run_id: str) -> Iterator[None]:
        """Hold an advisory transaction lock for one run across its advancement."""
        with self.engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SELECT pg_advisory_xact_lock(hashtext(:run_id))"), {"run_id": run_id})
                yield
            except BaseException:
                transaction.rollback()
                raise
            else:
                transaction.commit()

    @contextmanager
    def _local_lock(self, run_id: str) -> Iterator[None]:
        """Provide deterministic locking for the isolated SQLite contract test."""
        with self._local_locks_guard:
            lock = self._local_locks.setdefault(run_id, RLock())
        with lock:
            yield

    def _workspace(self, run_id: str) -> RunWorkspace:
        """Validate a run ID using the existing path policy and allocate no state."""
        paths = paths_for_run(self.artifact_root, run_id)
        return RunWorkspace(run_id=run_id, run_dir=paths.run_dir)

    @staticmethod
    def _row_from_snapshot(snapshot: RunSnapshot) -> RunRow:
        """Create a complete relational row graph from a domain checkpoint."""
        row = RunRow(run_id=snapshot.run_id)
        SqlAlchemyRunRepository._apply_snapshot(row, snapshot)
        return row

    @staticmethod
    def _apply_snapshot(row: RunRow, snapshot: RunSnapshot) -> None:
        """Copy all snapshot fields into an ORM row without domain dependencies."""
        row.state_version = snapshot.state_version
        row.subject = snapshot.subject
        row.inputs = snapshot.inputs
        row.status = snapshot.status
        row.current_stage = snapshot.current_stage
        row.created_at = _parse_timestamp(snapshot.created_at)
        row.updated_at = _parse_timestamp(snapshot.updated_at)
        existing = {stage.name: stage for stage in row.stages}
        for name, stage in snapshot.stages.items():
            stage_row = existing.pop(name, None) or RunStageRow(name=name)
            stage_row.status = stage.status
            stage_row.artifact_name = stage.artifact.name
            stage_row.message = stage.message
            stage_row.attempts = stage.attempts
            stage_row.started_at = _parse_optional_timestamp(stage.started_at)
            stage_row.finished_at = _parse_optional_timestamp(stage.finished_at)
            if stage_row not in row.stages:
                row.stages.append(stage_row)
        for stale_stage in existing.values():
            row.stages.remove(stale_stage)

    @staticmethod
    def _snapshot_from_row(row: RunRow) -> RunSnapshot:
        """Translate persisted rows back into the typed workflow checkpoint."""
        return RunSnapshot(
            state_version=row.state_version,
            run_id=row.run_id,
            subject=row.subject,
            inputs=row.inputs,
            status=cast(RunStatus, row.status),
            current_stage=row.current_stage,
            created_at=_format_timestamp(row.created_at),
            updated_at=_format_timestamp(row.updated_at),
            stages={
                stage.name: StageSnapshot(
                    status=stage.status,  # type: ignore[arg-type]
                    artifact=ArtifactReference(stage.artifact_name),
                    message=stage.message,
                    attempts=stage.attempts,
                    started_at=_format_optional_timestamp(stage.started_at),
                    finished_at=_format_optional_timestamp(stage.finished_at),
                )
                for stage in row.stages
            },
        )


def _parse_timestamp(value: str) -> datetime:
    """Parse the stable UTC ISO timestamp stored in the domain snapshot."""
    return datetime.fromisoformat(value)


def _parse_optional_timestamp(value: str | None) -> datetime | None:
    """Parse a nullable domain timestamp for an unfinished stage."""
    return _parse_timestamp(value) if value else None


def _format_timestamp(value: datetime) -> str:
    """Render a database timestamp using the existing snapshot wire format."""
    # SQLite (used only for the contract test) drops timezone information even
    # for a timezone-aware SQLAlchemy column. Treat that test representation as
    # UTC so it retains the domain contract used by PostgreSQL in production.
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat()


def _format_optional_timestamp(value: datetime | None) -> str | None:
    """Render a nullable database timestamp without inventing a completion time."""
    return _format_timestamp(value) if value else None
