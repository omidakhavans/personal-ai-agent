from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from personal_ai_agent.research_work import (
    ResearchWorkExecutor,
    ResearchWorkSettings,
    collect_local_evidence,
)
from personal_ai_agent.runtime import Orchestrator
from personal_ai_agent.stages import (
    STAGE_BLOCKED,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_PENDING,
    STAGE_RUNNING,
    MappingStageExecutor,
    RoutedStageExecutor,
    StageResult,
)
from personal_ai_agent.state import (
    RUN_BLOCKED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_RUNNING,
    paths_for_run,
    read_state,
    write_state,
)


class RuntimeTests(unittest.TestCase):
    def test_new_run_creates_directory_and_initializes_state(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            state = Orchestrator(runs_dir=runs_dir).start("My subject")

            paths = paths_for_run(runs_dir, state["run_id"])
            saved = read_state(paths.state_path)

            self.assertTrue(paths.run_dir.exists())
            self.assertEqual(saved["subject"], "My subject")
            self.assertEqual(saved["status"], RUN_COMPLETED)
            self.assertIn("research-work", saved["stages"])

    def test_successful_stage_progression_and_artifact_creation(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            state = Orchestrator(runs_dir=runs_dir).start("Tool calling")
            run_dir = paths_for_run(runs_dir, state["run_id"]).run_dir

            self.assertEqual(state["status"], RUN_COMPLETED)
            self.assertEqual(state["current_stage"], None)
            self.assertTrue((run_dir / "research-report.md").exists())
            self.assertTrue((run_dir / "x-draft.md").exists())
            self.assertTrue((run_dir / "state.json").exists())

    def test_failed_stage_stops_workflow(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            executor = MappingStageExecutor(
                {
                    "write-blog": StageResult(
                        status=STAGE_FAILED,
                        message="Template rendering crashed.",
                    )
                }
            )
            state = Orchestrator(runs_dir=runs_dir, executor=executor).start("Failure case")

            self.assertEqual(state["status"], RUN_FAILED)
            self.assertEqual(state["current_stage"], "write-blog")
            self.assertEqual(state["stages"]["write-blog"]["status"], STAGE_FAILED)
            self.assertEqual(state["stages"]["review-blog"]["status"], STAGE_PENDING)

    def test_blocked_stage_stops_without_marking_failure(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            executor = MappingStageExecutor(
                {
                    "research-work": StageResult(
                        status=STAGE_BLOCKED,
                        message="Insufficient verified work evidence.",
                    )
                }
            )
            state = Orchestrator(runs_dir=runs_dir, executor=executor).start("Unknown work")

            self.assertEqual(state["status"], RUN_BLOCKED)
            self.assertEqual(state["current_stage"], "research-work")
            self.assertEqual(state["stages"]["research-work"]["status"], STAGE_BLOCKED)
            self.assertEqual(state["stages"]["research-resources"]["status"], STAGE_PENDING)

    def test_resume_retries_interrupted_running_stage(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            first = Orchestrator(runs_dir=runs_dir).start("Resume subject")
            paths = paths_for_run(runs_dir, first["run_id"])
            state = read_state(paths.state_path)

            state["status"] = RUN_RUNNING
            state["current_stage"] = "write-blog"
            state["stages"]["write-blog"]["status"] = STAGE_RUNNING
            state["stages"]["write-blog"]["message"] = "Interrupted."
            state["stages"]["review-blog"]["status"] = STAGE_PENDING
            state["stages"]["write-linkedin"]["status"] = STAGE_PENDING
            state["stages"]["write-x"]["status"] = STAGE_PENDING
            write_state(paths.state_path, state)

            resumed = Orchestrator(runs_dir=runs_dir).resume(first["run_id"])

            self.assertEqual(resumed["status"], RUN_COMPLETED)
            self.assertEqual(resumed["stages"]["write-blog"]["status"], STAGE_COMPLETED)

    def test_resume_does_not_rerun_completed_stages(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            executor = MappingStageExecutor(
                {
                    "build-evidence-context": StageResult(
                        status=STAGE_BLOCKED,
                        message="No credible article angle.",
                    )
                }
            )
            state = Orchestrator(runs_dir=runs_dir, executor=executor).start("Partial run")
            paths = paths_for_run(runs_dir, state["run_id"])

            saved = read_state(paths.state_path)
            saved["status"] = RUN_RUNNING
            saved["stages"]["build-evidence-context"]["status"] = STAGE_PENDING
            write_state(paths.state_path, saved)

            resume_executor = MappingStageExecutor()
            resumed = Orchestrator(
                runs_dir=runs_dir,
                executor=resume_executor,
            ).resume(state["run_id"])

            self.assertEqual(resumed["status"], RUN_COMPLETED)
            self.assertEqual(resume_executor.calls[0], "build-evidence-context")
            self.assertNotIn("research-work", resume_executor.calls)
            self.assertNotIn("research-resources", resume_executor.calls)


class FakeModelClient:
    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        self.calls: list[dict[str, str]] = []

    def generate_json(self, *, model: str, instructions: str, input_text: str) -> dict[str, Any]:
        self.calls.append({"model": model, "instructions": instructions, "input": input_text})
        return self.report


def valid_research_report() -> dict[str, Any]:
    claim = {"status": "Verified", "claim": "A tool-calling feature is documented.", "evidence_ids": ["E1"]}
    return {
        "executive_summary": [claim],
        "what_was_implemented": [claim],
        "technical_decisions": [],
        "problems_encountered": [],
        "solutions_or_approaches": [],
        "technologies_and_concepts": ["tool calling"],
        "potential_lessons": [],
        "unknowns": ["Motivation is not established by the inspected evidence."],
    }


class ResearchWorkTests(unittest.TestCase):
    def test_collects_narrow_subject_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp)
            (repository / "README.md").write_text("# Demo\n\nTool calling powers the rewrite flow.\n", encoding="utf-8")
            (repository / "unrelated.md").write_text("Nothing relevant here.\n", encoding="utf-8")

            evidence = collect_local_evidence("What I learned about tool calling", repository)

            self.assertEqual(evidence.search_terms, ("tool", "calling"))
            self.assertEqual(evidence.items[0].reference, "README.md")
            self.assertIn("Tool calling", evidence.items[0].content)

    def test_real_research_stage_writes_grounded_report_then_pipeline_continues(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Demo\n\nTool calling powers the rewrite flow.\n", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            model = FakeModelClient(valid_research_report())
            research = ResearchWorkExecutor(
                settings=ResearchWorkSettings(repository=repository, model="test-model"),
                client=model,
            )

            state = Orchestrator(
                runs_dir=runs_dir,
                executor=RoutedStageExecutor(research_work=research),
            ).start("What I learned about tool calling")
            report = (paths_for_run(runs_dir, state["run_id"]).run_dir / "research-report.md").read_text(encoding="utf-8")

            self.assertEqual(state["status"], RUN_COMPLETED)
            self.assertEqual(len(model.calls), 1)
            self.assertIn("Verified: A tool-calling feature is documented. (Evidence: E1)", report)
            self.assertIn("`E1`: `README.md`", report)

    def test_insufficient_evidence_blocks_without_calling_model(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp) / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Unrelated project\n", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            model = FakeModelClient(valid_research_report())
            research = ResearchWorkExecutor(
                settings=ResearchWorkSettings(repository=repository, model="test-model"),
                client=model,
            )

            state = Orchestrator(
                runs_dir=runs_dir,
                executor=RoutedStageExecutor(research_work=research),
            ).start("Tool calling")

            self.assertEqual(state["status"], RUN_BLOCKED)
            self.assertEqual(state["stages"]["research-work"]["status"], STAGE_BLOCKED)
            self.assertEqual(model.calls, [])


if __name__ == "__main__":
    unittest.main()
