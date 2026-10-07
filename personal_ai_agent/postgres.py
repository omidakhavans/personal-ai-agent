"""SQLAlchemy persistence adapter for durable, queryable workflow snapshots.

The domain and orchestration layers only depend on ``RunRepository``.  This
module is an infrastructure adapter: it translates those records into rows and
keeps SQLAlchemy out of the workflow rules.
"""

from __future__ import annotations

import base64
import json
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
    UniqueConstraint,
    create_engine,
    select,
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

from .domain import ArtifactReference, RunSnapshot, RunStatus, StageSnapshot, utc_now
from .persistence import RunWorkspace
from .privacy import redact_sensitive_text
from .run_queries import (
    InvalidRunCursorError,
    RunDetail,
    RunEventView,
    RunListFilters,
    RunListItem,
    RunPage,
    RunQueryService,
    RunStageView,
)
from .stages import StageStatus
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
    events: Mapped[list[RunEventRow]] = relationship(
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


class RunEventRow(Base):
    """Immutable business-history entry, not a replacement for technical logs."""

    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_run_events_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stage_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    run: Mapped[RunRow] = relationship(back_populates="events")


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
            row = self._row_from_snapshot(snapshot)
            row.events.append(
                RunEventRow(
                    sequence=1,
                    event_type="run.created",
                    occurred_at=_parse_timestamp(snapshot.created_at),
                    schema_version=1,
                    payload={"workflow": "content"},
                )
            )
            session.add(row)
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
        """Checkpoint state and append its derived business events atomically."""
        if workspace.run_id != snapshot.run_id:
            raise ValueError("Workspace and snapshot run IDs must match.")
        with self._sessions.begin() as session:
            row = self._locked_row(session, workspace.run_id)
            if row is None:
                raise ValueError(f"Run {workspace.run_id!r} does not exist.")
            previous_status = row.status
            previous_stages = {
                stage.name: (stage.status, stage.attempts) for stage in row.stages
            }
            snapshot.updated_at = utc_now()
            self._apply_snapshot(row, snapshot)
            self._append_transition_events(
                row,
                previous_status=previous_status,
                previous_stages=previous_stages,
                snapshot=snapshot,
            )

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

    def _locked_row(self, session: Any, run_id: str) -> RunRow | None:
        """Load one run under a row lock so sequence allocation remains atomic."""
        statement = select(RunRow).where(RunRow.run_id == run_id)
        if self.engine.dialect.name == "postgresql":
            statement = statement.with_for_update()
        return cast(RunRow | None, session.scalar(statement))

    @staticmethod
    def _append_transition_events(
        row: RunRow,
        *,
        previous_status: str,
        previous_stages: dict[str, tuple[str, int]],
        snapshot: RunSnapshot,
    ) -> None:
        """Derive the small, stable event vocabulary from a checkpoint delta.

        Events are an immutable explanatory history.  The run row remains the
        authoritative latest snapshot, and logs/model transcripts remain out of
        this business history.
        """
        next_sequence = max((event.sequence for event in row.events), default=0) + 1
        occurred_at = _parse_timestamp(snapshot.updated_at)

        def append(
            event_type: str,
            *,
            stage_name: str | None = None,
            payload: dict[str, Any] | None = None,
        ) -> None:
            nonlocal next_sequence
            row.events.append(
                RunEventRow(
                    sequence=next_sequence,
                    event_type=event_type,
                    stage_name=stage_name,
                    occurred_at=occurred_at,
                    schema_version=1,
                    payload=_safe_event_payload(payload or {}),
                )
            )
            next_sequence += 1

        for name, stage in snapshot.stages.items():
            previous = previous_stages.get(name)
            if previous is None or previous == (stage.status, stage.attempts):
                continue
            previous_stage_status, previous_attempts = previous
            payload = {
                "from_status": previous_stage_status,
                "to_status": stage.status,
                "attempt": stage.attempts,
            }
            if stage.status == "running":
                append("step.started", stage_name=name, payload=payload)
            elif stage.status == "completed":
                append("step.completed", stage_name=name, payload=payload)
            elif stage.status == "blocked":
                append("step.blocked", stage_name=name, payload=payload)
            elif stage.status == "failed":
                append("step.failed", stage_name=name, payload=payload)
            elif stage.status == "awaiting_approval":
                append("approval.requested", stage_name=name, payload=payload)
            elif previous_attempts != stage.attempts:
                append("step.retry_scheduled", stage_name=name, payload=payload)

        if previous_status == snapshot.status:
            return
        status_payload = {"from_status": previous_status, "to_status": snapshot.status}
        if snapshot.status == "running":
            event_type = "approval.completed" if previous_status == "awaiting_approval" else "run.started"
        elif snapshot.status == "completed":
            event_type = "run.completed"
        elif snapshot.status == "blocked":
            event_type = "run.blocked"
        elif snapshot.status == "failed":
            event_type = "run.failed"
        elif snapshot.status == "awaiting_approval":
            event_type = "run.awaiting_approval"
        else:
            return
        append(event_type, stage_name=snapshot.current_stage, payload=status_payload)

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


class SqlAlchemyRunQueryService(RunQueryService):
    """Read durable run history without exposing SQLAlchemy outside this adapter."""

    def __init__(self, repository: SqlAlchemyRunRepository) -> None:
        """Reuse the repository's engine and session configuration for safe reads."""
        self._repository = repository

    def list_runs(
        self,
        *,
        filters: RunListFilters | None = None,
        limit: int = 25,
        cursor: str | None = None,
    ) -> RunPage:
        """Return newest-first keyset pages using stable creation time and ID order."""
        if not 1 <= limit <= 100:
            raise ValueError("Run query limit must be between 1 and 100.")
        filters = filters or RunListFilters()
        statement = select(RunRow).order_by(RunRow.created_at.desc(), RunRow.run_id.desc())
        if filters.status is not None:
            statement = statement.where(RunRow.status == filters.status)
        if filters.created_after is not None:
            statement = statement.where(RunRow.created_at >= _normalize_datetime(filters.created_after))
        if filters.created_before is not None:
            statement = statement.where(RunRow.created_at <= _normalize_datetime(filters.created_before))
        if cursor is not None:
            cursor_time, cursor_run_id = _decode_cursor(cursor)
            statement = statement.where(
                (RunRow.created_at < cursor_time)
                | ((RunRow.created_at == cursor_time) & (RunRow.run_id < cursor_run_id))
            )
        with self._repository._sessions() as session:
            rows = list(session.scalars(statement.limit(limit + 1)))
            page_rows = rows[:limit]
            items = tuple(self._list_item(row) for row in page_rows)
            next_cursor = (
                _encode_cursor(page_rows[-1].created_at, page_rows[-1].run_id)
                if len(rows) > limit and page_rows
                else None
            )
            return RunPage(items=items, next_cursor=next_cursor)

    def get_run_detail(self, run_id: str) -> RunDetail | None:
        """Return stages and ordered history for one run without artifact content."""
        with self._repository._sessions() as session:
            row = session.get(RunRow, run_id)
            if row is None:
                return None
            stages = tuple(
                RunStageView(
                    name=stage.name,
                    status=cast(StageStatus, stage.status),
                    artifact_name=stage.artifact_name,
                    attempts=stage.attempts,
                    started_at=_normalize_datetime(stage.started_at) if stage.started_at else None,
                    finished_at=_normalize_datetime(stage.finished_at) if stage.finished_at else None,
                    message=redact_sensitive_text(stage.message),
                )
                for stage in sorted(row.stages, key=lambda stage: stage.name)
            )
            events = tuple(self._event_view(event) for event in sorted(row.events, key=lambda event: event.sequence))
            return RunDetail(
                run_id=row.run_id,
                workflow="content",
                subject=redact_sensitive_text(row.subject),
                status=cast(RunStatus, row.status),
                created_at=_normalize_datetime(row.created_at),
                updated_at=_normalize_datetime(row.updated_at),
                current_step=row.current_stage,
                input_summary=_safe_input_summary(row.inputs),
                stages=stages,
                events=events,
            )

    @staticmethod
    def _list_item(row: RunRow) -> RunListItem:
        """Project one relational run into the intentionally compact list DTO."""
        events = sorted(row.events, key=lambda event: event.sequence)
        started = next((event.occurred_at for event in events if event.event_type == "run.started"), None)
        finished = next(
            (
                event.occurred_at
                for event in reversed(events)
                if event.event_type in {"run.completed", "run.failed", "run.blocked"}
            ),
            None,
        )
        started_at = _normalize_datetime(started) if started else None
        finished_at = _normalize_datetime(finished) if finished else None
        duration = (finished_at - started_at).total_seconds() if started_at and finished_at else None
        error_stage = next((stage for stage in row.stages if stage.status in {"failed", "blocked"}), None)
        model = row.inputs.get("model")
        return RunListItem(
            run_id=row.run_id,
            workflow="content",
            status=cast(RunStatus, row.status),
            created_at=_normalize_datetime(row.created_at),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
            current_step=row.current_stage,
            stage_attempt_count=sum(stage.attempts for stage in row.stages),
            error_summary=redact_sensitive_text(error_stage.message) if error_stage else None,
            model=model if isinstance(model, str) else None,
        )

    @staticmethod
    def _event_view(event: RunEventRow) -> RunEventView:
        """Render a durable event as a transport-independent, safe read model."""
        return RunEventView(
            sequence=event.sequence,
            event_type=event.event_type,
            occurred_at=_normalize_datetime(event.occurred_at),
            stage_name=event.stage_name,
            schema_version=event.schema_version,
            payload=_safe_event_payload(event.payload),
        )


def _safe_event_payload(value: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact strings before durable event storage or query output."""
    def clean(item: Any) -> Any:
        if isinstance(item, str):
            return redact_sensitive_text(item)
        if isinstance(item, dict):
            return {str(key): clean(nested) for key, nested in item.items()}
        if isinstance(item, list):
            return [clean(nested) for nested in item]
        return item

    return cast(dict[str, Any], clean(value))


def _safe_input_summary(inputs: dict[str, Any]) -> dict[str, Any]:
    """Expose only the existing shareable run-input labels in query results."""
    summary: dict[str, Any] = {}
    for key in ("repository", "model", "model_runtime"):
        value = inputs.get(key)
        if isinstance(value, str):
            summary[key] = redact_sensitive_text(value)
        elif isinstance(value, dict) and key == "model_runtime":
            summary[key] = _safe_event_payload(value)
    resources = inputs.get("resources")
    if isinstance(resources, list) and all(isinstance(resource, str) for resource in resources):
        summary["resources"] = [redact_sensitive_text(resource) for resource in resources]
    return summary


def _encode_cursor(created_at: datetime, run_id: str) -> str:
    """Encode the stable sort key as an opaque cursor for keyset pagination."""
    payload = json.dumps(
        {"created_at": _normalize_datetime(created_at).isoformat(), "run_id": run_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Validate and decode a cursor without treating browser input as trusted."""
    try:
        padding = "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(cursor + padding).decode("utf-8"))
        timestamp = value["created_at"]
        run_id = value["run_id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidRunCursorError("Run query cursor is invalid.") from exc
    if not isinstance(timestamp, str) or not isinstance(run_id, str):
        raise InvalidRunCursorError("Run query cursor is invalid.")
    return _normalize_datetime(datetime.fromisoformat(timestamp)), run_id


def _normalize_datetime(value: datetime) -> datetime:
    """Treat SQLite's test-only naive timestamps as UTC and normalize all reads."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


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
