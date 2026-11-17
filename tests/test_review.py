"""Test evidence validation and degraded reviews with replaceable model responses."""

import asyncio

import pytest

from mr_sentinel.config import Settings
from mr_sentinel.demo import SAMPLE, FixtureProvider
from mr_sentinel.diff import added_lines
from mr_sentinel.gitlab import render, safe
from mr_sentinel.orchestrator import review
from mr_sentinel.schemas import SecurityFindings, Summary


def settings(timeout: float = 1) -> Settings:
    return Settings(
        engine="vllm",
        model="fixture",
        base_url="http://model.test/v1",
        review_timeout_seconds=timeout,
    )


def test_diff_additions_ignore_removed_lines_and_context():
    patch = """diff --git a/x.py b/x.py
--- a/x.py
+++ b/x.py
@@ -8,3 +8,3 @@
 same
-old
+new
 same
"""
    assert added_lines(patch) == {("x.py", 9)}


async def test_high_evidence_sets_risk_floor():
    result = await review(SAMPLE, "", FixtureProvider(), settings())
    assert result.status == "complete"
    assert result.risk_score == 70
    assert {(row.path, row.line) for row in result.findings} == {("app.py", 2)}
    assert "Human review requested" in render(result, 70)


async def test_failed_specialist_does_not_yield_clean_review():
    class Incomplete(FixtureProvider):
        async def complete(self, system, user, schema):
            if schema is Summary:
                raise RuntimeError("fixture failure")
            return await super().complete(system, user, schema)

    result = await review(SAMPLE, "", Incomplete(), settings())
    assert result.status == "degraded"
    assert result.risk_score is None
    assert result.findings


async def test_hallucinated_line_is_discarded():
    class WrongLine(FixtureProvider):
        async def complete(self, system, user, schema):
            result = await super().complete(system, user, schema)
            if isinstance(result, SecurityFindings):
                result.findings[0].line = 999
            return result

    assert not (await review(SAMPLE, "", WrongLine(), settings())).findings


async def test_timeout_degrades():
    class Slow(FixtureProvider):
        async def complete(self, *args):
            await asyncio.sleep(1)
            return await super().complete(*args)

    assert (await review(SAMPLE, "", Slow(), settings(0.001))).risk_score is None


async def test_blank_diff_rejected():
    with pytest.raises(ValueError):
        await review(" ", "", FixtureProvider(), settings())


def test_markup_is_neutralized():
    assert "@someone" not in safe("@someone")
    assert "https://" not in safe("https://example.invalid")
