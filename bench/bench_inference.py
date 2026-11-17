"""Replay a fixed review workload and measure only completed responses as successful."""

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import httpx


async def run(args) -> dict:
    data = args.dataset.read_bytes()
    prompts = [json.loads(line)["diff"] for line in data.splitlines() if line.strip()]
    if not prompts or min(args.requests, args.concurrency) <= 0:
        raise ValueError("Need a nonempty workload and positive requests and concurrency")
    latency = []
    failures = 0
    jobs = iter(range(args.requests))
    async with httpx.AsyncClient(timeout=120) as client:

        async def worker() -> None:
            nonlocal failures
            for job in jobs:
                start = perf_counter()
                try:
                    response = await client.post(
                        args.url, json={"diff": prompts[job % len(prompts)]}
                    )
                    response.raise_for_status()
                    if response.json()["status"] != "complete":
                        raise ValueError("Incomplete review")
                except (httpx.HTTPError, ValueError, KeyError, TypeError):
                    failures += 1
                else:
                    latency.append((perf_counter() - start) * 1000)

        # A warm-up request is deliberately excluded from the latency distribution.
        warmup = await client.post(args.url, json={"diff": prompts[0]})
        warmup.raise_for_status()
        if warmup.json()["status"] != "complete":
            raise RuntimeError("Warm-up review degraded. Check the serving endpoint.")
        start = perf_counter()
        await asyncio.gather(*(worker() for _ in range(min(args.concurrency, args.requests))))
        seconds = perf_counter() - start
    ordered = sorted(latency)

    def percentile(q: float) -> float | None:
        return ordered[math.ceil(len(ordered) * q) - 1] if ordered else None

    return {
        "engine": args.engine,
        "model": args.model,
        "profile": args.profile,
        "workload_sha256": hashlib.sha256(data).hexdigest(),
        "requests": args.requests,
        "concurrency": args.concurrency,
        "failures": failures,
        "p50_ms": percentile(0.50),
        "p95_ms": percentile(0.95),
        "reviews_per_second": len(ordered) / seconds,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["vllm", "sglang"], required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--profile", required=True, help="Identify revision, hardware and server flags"
    )
    parser.add_argument("--dataset", type=Path, default=Path("evals/smoke.jsonl"))
    parser.add_argument("--url", default="http://127.0.0.1:8000/review")
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=2)
    print(json.dumps(asyncio.run(run(parser.parse_args())), indent=2))
