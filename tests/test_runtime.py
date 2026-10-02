from __future__ import annotations

import copy
import json
import os
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any
from unittest.mock import patch

from personal_ai_agent.evidence_context import (
    EvidenceContextExecutor,
    EvidenceContextSettings,
    collect_context_inputs,
    validate_context_brief,
)
from personal_ai_agent.research_resources import (
    ResearchResourcesSettings,
    ResourceReadError,
    ResourceResearchExecutor,
    _read_resource,
    collect_resources,
)
from personal_ai_agent.research_work import (
    ResearchWorkExecutor,
    ResearchWorkSettings,
    collect_local_evidence,
)
from personal_ai_agent.model_client import OpenAIResponsesClient
from personal_ai_agent.runtime import Orchestrator
from personal_ai_agent.stages import (
    STAGE_BLOCKED,
    STAGE_COMPLETED,
    STAGE_FAILED,
    STAGE_PENDING,
    STAGE_RUNNING,
    STAGE_SKIPPED,
    WORKFLOW_STAGES,
    MappingStageExecutor,
    RoutedStageExecutor,
    StageResult,
)
from personal_ai_agent.state import (
    RUN_BLOCKED,
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_RUNNING,
    StateError,
    paths_for_run,
    private_config_path,
    initial_state,
    read_state,
    read_private_config,
    write_private_config,
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
                        artifact="research-report.md",
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
                        artifact="context-brief.md",
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

    def test_success_without_the_expected_artifact_fails_the_run(self) -> None:
        with TemporaryDirectory() as tmp:
            state = Orchestrator(
                runs_dir=Path(tmp) / "runs",
                executor=MappingStageExecutor(
                    {"research-work": StageResult(status=STAGE_COMPLETED, message="Missing artifact.")}
                ),
            ).start("Artifact contract")

            self.assertEqual(state["status"], RUN_FAILED)
            self.assertIn("expected artifact", state["stages"]["research-work"]["message"])

    def test_invalid_run_id_is_rejected_before_path_construction(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(StateError, "invalid"):
                paths_for_run(Path(tmp) / "runs", "../outside")

    def test_corrupt_state_returns_a_clear_error(self) -> None:
        with TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text("{not-json", encoding="utf-8")

            with self.assertRaisesRegex(StateError, "corrupt"):
                read_state(state_path)

    def test_pre_hardening_state_is_migrated_when_read(self) -> None:
        with TemporaryDirectory() as tmp:
            old_state = initial_state("20261002-105024-1234abcd", "Old run")
            old_state.pop("state_version")
            for stage in old_state["stages"].values():
                stage.pop("attempts")
            state_path = Path(tmp) / "state.json"
            state_path.write_text(json.dumps(old_state), encoding="utf-8")

            migrated = read_state(state_path)

            self.assertEqual(migrated["state_version"], 2)
            self.assertTrue(all(stage["attempts"] == 0 for stage in migrated["stages"].values()))

    def test_private_resume_configuration_is_not_part_of_run_state(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            config = {
                "repository": "local-machine/project",
                "resources": ["local-machine/note.md"],
                "model": "test-model",
            }
            state = Orchestrator(runs_dir=runs_dir).start(
                "Private configuration",
                inputs={"repository": "local repository: project", "resources": ["local file: note.md"]},
                private_inputs=config,
            )
            persisted = read_state(paths_for_run(runs_dir, state["run_id"]).state_path)
            config_path = private_config_path(runs_dir, state["run_id"])

            self.assertNotIn("local-machine", json.dumps(persisted))
            self.assertEqual(read_private_config(runs_dir, state["run_id"]), config)
            self.assertEqual(os.stat(config_path).st_mode & 0o777, 0o600)

    def test_interrupted_stage_records_a_new_attempt_when_resumed(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            first = Orchestrator(runs_dir=runs_dir).start("Attempt tracking")
            paths = paths_for_run(runs_dir, first["run_id"])
            state = read_state(paths.state_path)
            state["status"] = RUN_RUNNING
            state["current_stage"] = "write-blog"
            state["stages"]["write-blog"]["status"] = STAGE_RUNNING
            write_state(paths.state_path, state)

            resumed = Orchestrator(runs_dir=runs_dir).resume(first["run_id"])

            self.assertEqual(resumed["stages"]["write-blog"]["attempts"], 2)


class FakeModelClient:
    def __init__(self, report: dict[str, Any]) -> None:
        self.report = report
        self.calls: list[dict[str, str]] = []

    def generate_json(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        self.calls.append({"model": model, "instructions": instructions, "input": input_text, "schema_name": schema_name})
        return self.report


def valid_research_report() -> dict[str, Any]:
    claim = {"status": "Verified", "claim": "A tool-calling feature is documented.", "evidence_ids": ["E1"]}
    return {
        "executive_summary": [claim],
        "what_was_implemented": [claim],
        "technical_decisions": [],
        "problems_encountered": [],
        "solutions_or_approaches": [],
        "technologies_and_concepts": [
            {"status": "Verified", "claim": "The repository uses tool calling.", "evidence_ids": ["E1"]}
        ],
        "potential_lessons": [],
        "unknowns": ["Motivation is not established by the inspected evidence."],
    }


def valid_resource_report() -> dict[str, Any]:
    claim = {
        "status": "Source fact",
        "claim": "The supplied note defines tool calling as a model capability.",
        "resource_ids": ["R1"],
    }
    return {
        "executive_summary": [claim],
        "important_concepts": [claim],
        "technical_explanations": [],
        "approaches_or_patterns": [],
        "important_terminology": [],
        "useful_examples": [],
        "connections_to_subject": [],
        "conflicts": [],
        "potential_lessons": [],
        "unknowns": ["The note does not describe a production implementation."],
    }


def valid_context_brief() -> dict[str, Any]:
    work_claim = {
        "label": "Verified work evidence",
        "claim": "The repository documents tool calling.",
        "work_evidence_ids": ["E1"],
        "resource_ids": [],
    }
    connection_claim = {
        "label": "Interpretation",
        "claim": "The work and supplied note both concern tool calling.",
        "work_evidence_ids": ["E1"],
        "resource_ids": ["R1"],
    }
    empty_sections = {
        "verified_external_knowledge": [],
        "technical_decisions_and_reasoning": [],
        "problems_or_failures_encountered": [],
        "lessons_learned": [],
        "claims_not_fact": [],
        "conflicts_or_uncertainty": [],
        "information_intentionally_excluded": [],
    }
    return {
        "executive_summary": [work_claim],
        "verified_work_evidence": [work_claim],
        "connections_between_work_and_resources": [connection_claim],
        "strong_content_angles": [connection_claim],
        "recommended_article_focus": {
            "status": "ready",
            "focus": "Explain the grounded lesson from tool calling.",
            "work_evidence_ids": ["E1"],
            "resource_ids": ["R1"],
        },
        "unknowns": ["The supplied reports do not establish production impact."],
        **empty_sections,
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

    def test_redacts_common_credentials_before_the_model_receives_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            repository = Path(tmp)
            (repository / "README.md").write_text(
                f"Tool calling uses api_key={'sk-' + 'thisisnotarealkeyvalue123456'}\n",
                encoding="utf-8",
            )

            evidence = collect_local_evidence("Tool calling", repository)

            self.assertIn("[REDACTED]", evidence.items[0].content)
            self.assertNotIn("sk-" + "thisisnotarealkeyvalue123456", evidence.items[0].content)


class ResearchResourcesTests(unittest.TestCase):
    def test_collects_explicit_local_resource(self) -> None:
        with TemporaryDirectory() as tmp:
            resource_path = Path(tmp) / "tool-calling.md"
            resource_path.write_text("# Tool calling\n\nA model can request a tool.\n", encoding="utf-8")

            bundle = collect_resources((str(resource_path),))

            self.assertEqual(bundle.resources[0].identifier, "R1")
            self.assertEqual(bundle.resources[0].title, "tool-calling.md")
            self.assertIn("request a tool", bundle.resources[0].content)
            self.assertEqual(bundle.inaccessible, ())

    def test_resource_stage_writes_report_for_supplied_local_resource(self) -> None:
        with TemporaryDirectory() as tmp:
            resource_path = Path(tmp) / "tool-calling.md"
            resource_path.write_text("# Tool calling\n\nA model can request a tool.\n", encoding="utf-8")
            repository = Path(tmp) / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("Tool calling is used here.\n", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            work_model = FakeModelClient(valid_research_report())
            resource_model = FakeModelClient(valid_resource_report())
            work = ResearchWorkExecutor(
                settings=ResearchWorkSettings(repository=repository, model="test-model"),
                client=work_model,
            )
            resources = ResourceResearchExecutor(
                settings=ResearchResourcesSettings(references=(str(resource_path),), model="test-model"),
                client=resource_model,
            )

            state = Orchestrator(
                runs_dir=runs_dir,
                executor=RoutedStageExecutor(
                    research_work=work,
                    research_resources=resources,
                ),
            ).start("Tool calling")
            report = (paths_for_run(runs_dir, state["run_id"]).run_dir / "resources-report.md").read_text(encoding="utf-8")

            self.assertEqual(state["stages"]["research-resources"]["status"], STAGE_COMPLETED)
            self.assertEqual(len(resource_model.calls), 1)
            self.assertIn("Sources: R1", report)
            self.assertIn("tool-calling.md", report)

    def test_resource_stage_skips_when_no_resources_are_supplied(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            resource_model = FakeModelClient(valid_resource_report())
            resources = ResourceResearchExecutor(
                settings=ResearchResourcesSettings(references=(), model="test-model"),
                client=resource_model,
            )

            run_dir = runs_dir / "one"
            run_dir.mkdir(parents=True)
            result = resources.execute(
                stage=next(stage for stage in WORKFLOW_STAGES if stage.name == "research-resources"),
                subject="Tool calling",
                run_dir=run_dir,
            )

            self.assertEqual(result.status, STAGE_SKIPPED)
            self.assertEqual(resource_model.calls, [])
            self.assertIn("No resources were supplied", (run_dir / "resources-report.md").read_text(encoding="utf-8"))

    def test_resource_stage_blocks_when_all_supplied_resources_are_inaccessible(self) -> None:
        with TemporaryDirectory() as tmp:
            runs_dir = Path(tmp) / "runs"
            resource_model = FakeModelClient(valid_resource_report())
            resources = ResourceResearchExecutor(
                settings=ResearchResourcesSettings(
                    references=(str(Path(tmp) / "missing.md"),),
                    model="test-model",
                ),
                client=resource_model,
            )
            run_dir = runs_dir / "one"
            run_dir.mkdir(parents=True)

            result = resources.execute(
                stage=next(stage for stage in WORKFLOW_STAGES if stage.name == "research-resources"),
                subject="Tool calling",
                run_dir=run_dir,
            )

            self.assertEqual(result.status, STAGE_BLOCKED)
            self.assertEqual(resource_model.calls, [])
            self.assertIn("could not be inspected", (run_dir / "resources-report.md").read_text(encoding="utf-8"))

    def test_rejects_insecure_and_private_network_urls_before_fetching(self) -> None:
        with self.assertRaisesRegex(ResourceReadError, "HTTPS"):
            _read_resource("http://example.com/reference")
        with self.assertRaisesRegex(ResourceReadError, "could not be fetched"):
            _read_resource("https://127.0.0.1/reference")

    def test_local_resource_reference_is_safe_to_render(self) -> None:
        with TemporaryDirectory() as tmp:
            resource_path = Path(tmp) / "private-note.md"
            resource_path.write_text("Tool calling note", encoding="utf-8")

            bundle = collect_resources((str(resource_path),))

            self.assertEqual(bundle.resources[0].reference, "local file: private-note.md")
            self.assertNotIn(str(Path(tmp)), bundle.resources[0].reference)


class EvidenceContextTests(unittest.TestCase):
    def test_context_stage_writes_traceable_brief(self) -> None:
        with TemporaryDirectory() as tmp:
            resource_path = Path(tmp) / "tool-calling.md"
            resource_path.write_text("# Tool calling\n\nA model can request a tool.\n", encoding="utf-8")
            repository = Path(tmp) / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("Tool calling is used here.\n", encoding="utf-8")
            runs_dir = Path(tmp) / "runs"
            work = ResearchWorkExecutor(
                settings=ResearchWorkSettings(repository=repository, model="test-model"),
                client=FakeModelClient(valid_research_report()),
            )
            resources = ResourceResearchExecutor(
                settings=ResearchResourcesSettings(references=(str(resource_path),), model="test-model"),
                client=FakeModelClient(valid_resource_report()),
            )
            context_model = FakeModelClient(valid_context_brief())
            context = EvidenceContextExecutor(
                settings=EvidenceContextSettings(model="test-model"),
                client=context_model,
            )

            state = Orchestrator(
                runs_dir=runs_dir,
                executor=RoutedStageExecutor(
                    research_work=work,
                    research_resources=resources,
                    evidence_context=context,
                ),
            ).start("Tool calling")
            report = (paths_for_run(runs_dir, state["run_id"]).run_dir / "context-brief.md").read_text(encoding="utf-8")

            self.assertEqual(state["stages"]["build-evidence-context"]["status"], STAGE_COMPLETED)
            self.assertEqual(len(context_model.calls), 1)
            self.assertIn("Work: E1; Resources: R1", report)
            self.assertIn("Work evidence `E1`", report)
            self.assertIn("External resource `R1`", report)

    def test_context_stage_blocks_when_work_report_is_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            model = FakeModelClient(valid_context_brief())
            context = EvidenceContextExecutor(
                settings=EvidenceContextSettings(model="test-model"),
                client=model,
            )

            result = context.execute(
                stage=next(stage for stage in WORKFLOW_STAGES if stage.name == "build-evidence-context"),
                subject="Tool calling",
                run_dir=run_dir,
            )

            self.assertEqual(result.status, STAGE_BLOCKED)
            self.assertEqual(model.calls, [])
            self.assertIn("Work research report is missing", (run_dir / "context-brief.md").read_text(encoding="utf-8"))

    def test_context_validation_rejects_an_invented_evidence_id(self) -> None:
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "research-report.md").write_text(
                "# Research Report\n\n## Evidence References\n\n- `E1`: `README.md`\n",
                encoding="utf-8",
            )
            (run_dir / "resources-report.md").write_text(
                "# Resource Research Report\n\n## Source References\n\n- `R1`: `notes.md`\n",
                encoding="utf-8",
            )
            brief = valid_context_brief()
            brief["verified_work_evidence"][0]["work_evidence_ids"] = ["E999"]

            with self.assertRaisesRegex(RuntimeError, "unknown work evidence IDs"):
                validate_context_brief(brief, collect_context_inputs(run_dir))


class ModelClientTests(unittest.TestCase):
    def test_requests_bounded_structured_output(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return b'{"output": [{"content": [{"type": "output_text", "text": "{}"}]}]}'

        client = OpenAIResponsesClient("test-key", max_output_tokens=321)
        with patch("personal_ai_agent.model_client.urllib.request.urlopen", return_value=Response()) as mocked_open:
            self.assertEqual(
                client.generate_json(
                    model="test-model",
                    instructions="Return JSON.",
                    input_text="bounded input",
                    schema_name="test_schema",
                    schema={"type": "object", "additionalProperties": False, "properties": {}},
                ),
                {},
            )

        payload = json.loads(mocked_open.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["max_output_tokens"], 321)


if __name__ == "__main__":
    unittest.main()
