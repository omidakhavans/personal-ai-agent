from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from personal_ai_agent.runtime import Orchestrator
from personal_ai_agent.stages import (
    STAGE_BLOCKED,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_PENDING,
    STAGE_RUNNING,
    MappingStageExecutor,
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


if __name__ == "__main__":
    unittest.main()
