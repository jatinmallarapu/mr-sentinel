"""Index added lines so model findings can cite evidence in the submitted revision."""

import re

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def added_lines(diff: str) -> set[tuple[str, int]]:
    path = ""
    line: int | None = None
    result: set[tuple[str, int]] = set()
    for row in diff.splitlines():
        if row.startswith("diff --git "):
            path = ""
            line = None
        elif row.startswith("+++ ") and line is None:
            target = row[4:].split("\t", 1)[0]
            path = target.removeprefix("b/") if target != "/dev/null" else ""
        elif match := HUNK.match(row):
            line = int(match[1])
        elif line is not None and path:
            if row.startswith("+"):
                result.add((path, line))
                line += 1
            elif row.startswith(" "):
                line += 1
    return result
