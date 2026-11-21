"""Benchmark real TheraSim patient/evaluator agents with synthetic cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import statistics
import subprocess
import sys
import time
from typing import Any
from urllib.parse import urlsplit


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import ProviderConfig, validate_provider_url  # noqa: E402
from app.core.hardware import assess_hardware  # noqa: E402
from app.llm.client import (  # noqa: E402
    OpenAICompatibleClient,
    ProviderConnectionError,
    ProviderResponseError,
)
from app.llm.evaluator_agent import (  # noqa: E402
    DEFAULT_EVALUATOR_MAX_TOKENS,
    EvaluatorAgent,
    EvaluatorAgentError,
    LONGITUDINAL_EVALUATOR_SYSTEM_PROMPT,
)
from app.llm.patient_agent import (  # noqa: E402
    DEFAULT_PATIENT_AGENT_MAX_TOKENS,
    PatientAgent,
    PatientAgentError,
)
from app.services.patient_context import (  # noqa: E402
    FrozenJSONObject,
    PatientContext,
    PatientIdentity,
    PatientState,
    PatientStateVariable,
    PatientTranscriptMessage,
    RestrictedProfileContext,
    STATE_VARIABLES,
)


CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "english_workplace_values",
        "language": "en",
        "concern": "avoiding speaking up in team meetings",
        "therapist_prompt": (
            "What goes through your mind just before you decide not to speak "
            "in a team meeting?"
        ),
        "transcript": [
            (
                "therapist",
                "Could we explore what happens just before you decide not to "
                "speak in meetings?",
            ),
            ("patient", "I imagine everyone will notice that I am nervous."),
            (
                "therapist",
                "What do you notice in your body when that thought appears?",
            ),
            ("patient", "My chest gets tight and I look down."),
            (
                "therapist",
                "What kind of colleague do you want to be even when anxiety "
                "shows up?",
            ),
        ],
    },
    {
        "id": "persian_workplace_values",
        "language": "fa",
        "concern": "دوری از صحبت کردن در جلسه‌های کاری",
        "therapist_prompt": (
            "وقتی در جلسهٔ کاری تصمیم می‌گیرید صحبت نکنید، چه چیزی از "
            "ذهن‌تان می‌گذرد؟"
        ),
        "transcript": [
            (
                "therapist",
                "می‌توانیم بررسی کنیم درست پیش از اینکه در جلسه صحبت نکنید "
                "چه اتفاقی می‌افتد؟",
            ),
            ("patient", "فکر می‌کنم همه متوجه اضطرابم می‌شوند."),
            (
                "therapist",
                "وقتی این فکر می‌آید، در بدنتان چه چیزی متوجه می‌شوید؟",
            ),
            ("patient", "قفسهٔ سینه‌ام سفت می‌شود و نگاهم را پایین می‌اندازم."),
            (
                "therapist",
                "حتی وقتی اضطراب هست، دوست دارید چه جور همکاری باشید؟",
            ),
        ],
    },
)


class ObservedClient:
    """Measure provider call time and token counts without retaining text."""

    def __init__(self, client: OpenAICompatibleClient) -> None:
        self.client = client
        self.config = client.config
        self.last_call: dict[str, Any] = {}

    @property
    def supports_json_schema(self) -> bool:
        return self.client.supports_json_schema

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            response = self.client.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        finally:
            elapsed = time.perf_counter() - started
            self.last_call = {"seconds": round(elapsed, 3)}
        self.last_call.update(
            {
                "usage": response.get("usage"),
                "finish_reason": response.get("finish_reason"),
            }
        )
        return response


def _patient_context(case: dict[str, Any], repeat: int) -> PatientContext:
    empty = FrozenJSONObject(())
    session_id = f"synthetic-{case['id']}-{repeat}"
    therapist_message = PatientTranscriptMessage(
        message_id=f"{session_id}-therapist-1",
        session_id=session_id,
        session_number=1,
        sequence_number=1,
        role="therapist",
        content=case["therapist_prompt"],
        created_at="2026-01-01T00:00:00Z",
    )
    return PatientContext(
        case_id=f"synthetic-{case['id']}",
        case_version_id="synthetic-v1",
        run_id=f"{session_id}-run",
        session_id=session_id,
        session_number=1,
        language=case["language"],
        modality="ACT",
        public_identity=PatientIdentity(
            display_name="Ava",
            age=29,
            occupation="office worker",
            presenting_concerns=(case["concern"],),
            initial_disclosure=None,
        ),
        restricted_profile=RestrictedProfileContext(
            clinical_formulation=empty,
            relevant_personal_history=empty,
            maintaining_factors=(),
            avoidance_patterns=(),
            hypothesized_functions=empty,
            initial_safety_baseline=empty,
            patient_simulation_instructions=(
                "This is a fictional educational scenario. "
                "Do not give clinical advice."
            ),
        ),
        relevant_case_facts=(),
        current_state=PatientState(
            snapshot_id=f"{session_id}-state",
            state_schema_version="1",
            values=tuple(
                PatientStateVariable(name=name, value=1)
                for name in sorted(STATE_VARIABLES)
            ),
        ),
        longitudinal_memory=(),
        recent_transcript=(),
        therapist_message=therapist_message,
    )


def _evaluation_transcript(
    case: dict[str, Any],
    repeat: int,
) -> list[dict[str, object]]:
    session_id = f"synthetic-eval-{case['id']}-{repeat}"
    return [
        {
            "message_id": f"{session_id}-{index}",
            "session_id": session_id,
            "role": role,
            "content": content,
        }
        for index, (role, content) in enumerate(case["transcript"], start=1)
    ]


def _usage_counts(usage: object) -> dict[str, int]:
    if not isinstance(usage, dict):
        return {}
    return {
        key: value
        for key, value in usage.items()
        if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
        and isinstance(value, int)
        and not isinstance(value, bool)
    }


def _ollama_residency(models: set[str]) -> list[dict[str, str]]:
    executable = shutil.which("ollama")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "ps"],
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    residency = []
    for line in result.stdout.splitlines()[1:]:
        match = re.match(
            r"^\s*(\S+)\s+\S+\s+([\d.]+\s+\S+)\s+"
            r"(\d+%\s+(?:GPU|CPU|GPU/CPU))\s+(\d+)\s+(.+?)\s*$",
            line,
        )
        if match and match.group(1) in models:
            residency.append(
                {
                    "model": match.group(1),
                    "size": match.group(2),
                    "processor": match.group(3),
                    "context": match.group(4),
                }
            )
    return residency


def _residency_for(model: str) -> dict[str, str] | None:
    return next(
        (
            item
            for item in _ollama_residency({model})
            if item["model"] == model
        ),
        None,
    )


def _run_patient(
    agent: PatientAgent,
    observed: ObservedClient,
    case: dict[str, Any],
    repeat: int,
) -> dict[str, Any]:
    try:
        result = agent.generate_response(_patient_context(case, repeat))
        return {
            "role": "patient",
            "case": case["id"],
            "repeat": repeat,
            "success": True,
            "latency_seconds": observed.last_call.get("seconds"),
            "usage": _usage_counts(observed.last_call.get("usage")),
            "output_characters": len(result.output.content),
            "finish_reason": result.finish_reason,
            "model_residency": _residency_for(agent.model),
        }
    except (PatientAgentError, ProviderConnectionError, ProviderResponseError) as exc:
        return {
            "role": "patient",
            "case": case["id"],
            "repeat": repeat,
            "success": False,
            "latency_seconds": observed.last_call.get("seconds"),
            "model_residency": _residency_for(agent.model),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _run_evaluator(
    agent: EvaluatorAgent,
    observed: ObservedClient,
    rubric: dict[str, object],
    rubric_document: str,
    case: dict[str, Any],
    repeat: int,
) -> dict[str, Any]:
    try:
        report = agent.evaluate(
            _evaluation_transcript(case, repeat),
            rubric_definition=rubric,
            rubric_document=rubric_document,
        )
        return {
            "role": "evaluator",
            "case": case["id"],
            "repeat": repeat,
            "success": True,
            "latency_seconds": observed.last_call.get("seconds"),
            "usage": _usage_counts(observed.last_call.get("usage")),
            "competency_count": len(report.competencies),
            "evidence_item_count": sum(
                len(competency.evidence)
                for competency in report.competencies
            ),
            "finish_reason": observed.last_call.get("finish_reason"),
            "model_residency": _residency_for(agent.model),
        }
    except (
        EvaluatorAgentError,
        ProviderConnectionError,
        ProviderResponseError,
    ) as exc:
        return {
            "role": "evaluator",
            "case": case["id"],
            "repeat": repeat,
            "success": False,
            "latency_seconds": observed.last_call.get("seconds"),
            "model_residency": _residency_for(agent.model),
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _summarize(results: list[dict[str, Any]]) -> dict[str, object]:
    summary: dict[str, object] = {}
    for role in ("patient", "evaluator"):
        selected = [item for item in results if item["role"] == role]
        latencies = [
            item["latency_seconds"]
            for item in selected
            if isinstance(item.get("latency_seconds"), (int, float))
        ]
        summary[role] = {
            "successes": sum(item["success"] for item in selected),
            "failures": sum(not item["success"] for item in selected),
            "runs": len(selected),
            "mean_latency_seconds": (
                round(statistics.mean(latencies), 3) if latencies else None
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="")
    parser.add_argument("--patient-model", default="")
    parser.add_argument("--evaluator-model", default="")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434/v1")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20 or not 1 <= args.timeout <= 600:
        parser.error("repeats must be 1..20 and timeout must be 1..600 seconds")

    try:
        base_url = validate_provider_url(args.base_url)
    except ValueError as exc:
        parser.error(str(exc))
    parsed = urlsplit(base_url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Benchmarking remote providers is disabled.")

    fallback_model = args.model.strip()
    patient_model = args.patient_model.strip() or fallback_model
    evaluator_model = args.evaluator_model.strip() or fallback_model
    if not patient_model or not evaluator_model:
        parser.error("Set --model or both role-specific model options.")

    provider = ProviderConfig(
        name="ollama",
        base_url=base_url,
        model=fallback_model or patient_model,
    )
    observed = ObservedClient(
        OpenAICompatibleClient(provider, timeout=args.timeout)
    )
    patient_agent = PatientAgent(
        observed,
        model=patient_model,
        max_tokens=DEFAULT_PATIENT_AGENT_MAX_TOKENS,
    )
    evaluator_agent = EvaluatorAgent(
        observed,
        model=evaluator_model,
        max_tokens=DEFAULT_EVALUATOR_MAX_TOKENS,
    )
    rubric, rubric_document, _ = evaluator_agent.load_rubric()

    results = []
    for repeat in range(1, args.repeats + 1):
        for case in CASES:
            results.append(
                _run_patient(patient_agent, observed, case, repeat)
            )
            results.append(
                _run_evaluator(
                    evaluator_agent,
                    observed,
                    rubric,
                    rubric_document,
                    case,
                    repeat,
                )
            )

    origin = f"{parsed.scheme}://{parsed.netloc}"
    report = {
        "provider": "ollama",
        "provider_endpoint": origin,
        "patient_model": patient_model,
        "evaluator_model": evaluator_model,
        "structured_evaluator_output": observed.supports_json_schema,
        "repeats": args.repeats,
        "cases": [case["id"] for case in CASES],
        "hardware": assess_hardware(ollama_base_url=origin),
        "ollama_residency": list(
            {
                json.dumps(residency, sort_keys=True): residency
                for result in results
                if (residency := result.get("model_residency"))
            }.values()
        ),
        "summary": _summarize(results),
        "results": results,
        "limitations": [
            "Cases and transcripts are synthetic; no clinical validity is assessed.",
            "Patient language quality and persona fidelity require human review.",
            "A schema-valid evaluator report does not establish rating accuracy.",
            "Results apply only to the exact model tags and hardware reported.",
        ],
    }
    serialized = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
        print(f"Benchmark report written to {args.output}")
    else:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
