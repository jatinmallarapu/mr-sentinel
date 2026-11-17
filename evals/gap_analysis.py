"""Group misses by documented category while keeping degraded cases visible."""

import argparse
import json
from collections import Counter
from pathlib import Path


def buckets(report: dict) -> Counter:
    return Counter(
        (
            case["category"],
            "degraded"
            if case["predicted"] is None
            else "missed risk"
            if case["label"]
            else "false alarm",
        )
        for case in report["cases"]
        if case["predicted"] is not case["label"]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    report = json.loads(parser.parse_args().report.read_text(encoding="utf-8"))
    print(
        json.dumps(
            [
                {"category": cat, "type": kind, "count": count}
                for (cat, kind), count in buckets(report).most_common()
            ],
            indent=2,
        )
    )
