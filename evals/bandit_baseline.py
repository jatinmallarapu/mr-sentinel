"""Run Bandit against complete added fixture files and score the resulting alerts."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter


def added_file(diff: str) -> str:
    # This baseline intentionally supports whole-file additions only. Partial
    # patches cannot be turned into a faithful Python AST without a checkout.
    if diff.count("diff --git ") != 1 or "\n@@ -0,0 " not in diff:
        raise ValueError("Bandit fixture baseline requires a single added Python file")
    return (
        "\n".join(
            line[1:]
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        + "\n"
    )


def evaluate(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError("No fixture rows")
    counts = dict.fromkeys(("tp", "fp", "fn", "tn"), 0)
    times = []
    with TemporaryDirectory() as directory:
        fixture = Path(directory, "fixture.py")
        for row in rows:
            fixture.write_text(added_file(row["diff"]), encoding="utf-8")
            start = perf_counter()
            run = subprocess.run(
                [sys.executable, "-m", "bandit", "-q", "-f", "json", str(fixture)],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            times.append((perf_counter() - start) * 1000)
            report = json.loads(run.stdout)
            if run.returncode not in (0, 1) or report["errors"]:
                raise RuntimeError(f"Bandit did not scan fixture {row['id']}")
            predicted = bool(report["results"])
            counts[
                ("tp" if predicted else "fn")
                if row["vulnerable"]
                else ("fp" if predicted else "tn")
            ] += 1
    tp, fp, fn = (counts[k] for k in ("tp", "fp", "fn"))
    return {
        "examples": len(rows),
        "confusion": counts,
        "precision": tp / (tp + fp) if tp + fp else 0,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
        "mean_ms": sum(times) / len(times),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("evals/smoke.jsonl"))
    print(json.dumps(evaluate(parser.parse_args().dataset), indent=2))
