"""Fan out bounded specialist calls and surface incomplete work explicitly."""

import asyncio
import json
from importlib.resources import files

from .config import Settings
from .diff import added_lines
from .metrics import AGENT_ERRORS, REVIEW_LATENCY, REVIEW_OUTCOMES
from .providers.base import ModelProvider, ProviderError
from .schemas import Judgment, Review, SecurityFindings, Summary, TestAssessment

PROMPTS = ("security", "tests", "summarizer", "judge")
RISK_FLOOR = {"low": 10, "medium": 40, "high": 70, "critical": 90}


def prompt(name: str) -> str:
    return files("mr_sentinel").joinpath("prompts", f"{name}.md").read_text(encoding="utf-8")


async def review(
    diff: str, scanner_summary: str, provider: ModelProvider, settings: Settings
) -> Review:
    if not diff.strip() or len(diff) > settings.max_diff_chars:
        raise ValueError("Diff is empty or exceeds the configured review budget")
    payload = json.dumps({"diff": diff, "scanner_summary": scanner_summary[:4000]})
    with REVIEW_LATENCY.time():
        try:
            async with asyncio.timeout(settings.review_timeout_seconds):
                sec, tests, summ = await asyncio.gather(
                    provider.complete(prompt("security"), payload, SecurityFindings),
                    provider.complete(prompt("tests"), payload, TestAssessment),
                    provider.complete(prompt("summarizer"), payload, Summary),
                    return_exceptions=True,
                )
                errors = [
                    name
                    for name, value in zip(PROMPTS, (sec, tests, summ))
                    if isinstance(value, Exception)
                ]
                for name in errors:
                    AGENT_ERRORS.labels(name).inc()
                evidence = added_lines(diff)
                findings = (
                    [f for f in sec.findings if (f.path, f.line) in evidence]
                    if isinstance(sec, SecurityFindings)
                    else []
                )
                missing = (
                    [x[:300] for x in tests.missing_tests]
                    if isinstance(tests, TestAssessment)
                    else []
                )
                summary = summ.summary if isinstance(summ, Summary) else "Summary unavailable."
                score = None
                rationale = "Specialist results are incomplete." if errors else ""
                if not errors:
                    try:
                        judge_data = json.dumps(
                            {
                                "summary": summary,
                                "missing_tests": missing,
                                "findings": [f.model_dump() for f in findings],
                            }
                        )
                        judge = await provider.complete(prompt("judge"), judge_data, Judgment)
                        risk_floor = max((RISK_FLOOR[f.severity] for f in findings), default=0)
                        score = max(risk_floor, judge.risk_score)
                        rationale = judge.rationale
                    except ProviderError:
                        AGENT_ERRORS.labels("judge").inc()
                        rationale = "Judgment unavailable."
                result = Review(
                    status="complete" if score is not None else "degraded",
                    summary=summary,
                    findings=findings,
                    missing_tests=missing,
                    risk_score=score,
                    rationale=rationale,
                )
        except TimeoutError:
            result = Review(
                status="degraded",
                summary="Review timed out.",
                findings=[],
                missing_tests=[],
                risk_score=None,
                rationale="Time budget exhausted.",
            )
        REVIEW_OUTCOMES.labels(result.status).inc()
        return result
