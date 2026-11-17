"""Score a frozen JSONL set through the real review path or the CI fixture provider."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import time
from pathlib import Path

import httpx

from mr_sentinel.config import load_settings
from mr_sentinel.demo import FixtureProvider
from mr_sentinel.orchestrator import review
from mr_sentinel.providers.openai_compat import OpenAICompatProvider


async def evaluate(args) -> dict:
    source = args.dataset.read_bytes()
    rows = [json.loads(line) for line in source.splitlines() if line.strip()]
    if not rows or len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Dataset must contain unique case IDs")
    settings = load_settings()
    records = []
    async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
        provider = (
            FixtureProvider()
            if args.fixture
            else OpenAICompatProvider(
                client, str(settings.base_url), settings.model, os.environ.get("MODEL_API_KEY", "")
            )
        )
        for row in rows:
            started = time.perf_counter()
            result = await review(row["diff"], row.get("scanner_summary", ""), provider, settings)
            predicted = (
                None if result.risk_score is None else result.risk_score >= settings.risk_threshold
            )
            records.append(
                {
                    "id": row["id"],
                    "label": row["vulnerable"],
                    "predicted": predicted,
                    "category": row["category"],
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }
            )
    tp = sum(r["label"] is True and r["predicted"] is True for r in records)
    fp = sum(r["label"] is False and r["predicted"] is True for r in records)
    fn = sum(r["label"] is True and r["predicted"] is not True for r in records)
    tn = sum(r["label"] is False and r["predicted"] is False for r in records)
    latency = sorted(r["latency_ms"] for r in records)
    return {
        "dataset_sha256": hashlib.sha256(source).hexdigest(),
        "model": provider.name,
        "engine": "fixture" if args.fixture else settings.engine,
        "examples": len(rows),
        "threshold": settings.risk_threshold,
        "accuracy": (tp + tn) / len(rows),
        "precision": tp / (tp + fp) if tp + fp else 0,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "p95_ms": latency[math.ceil(len(latency) * 0.95) - 1],
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "degraded": sum(r["predicted"] is None for r in records),
        "cases": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evals/smoke.jsonl"))
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-if-f1-below", type=float, default=0.75)
    args = parser.parse_args()
    result = asyncio.run(evaluate(args))
    report = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
    raise SystemExit(2 if result["degraded"] or result["f1"] < args.fail_if_f1_below else 0)
