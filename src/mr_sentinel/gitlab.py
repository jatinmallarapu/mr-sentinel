"""Fetch bounded diffs and write one advisory note through a fixed GitLab origin."""

import re

import httpx

from .schemas import Review

MARKUP = re.compile(r"[\\`*_{}\[\]()<>#+.!|@&]")


def safe(text: str) -> str:
    # Suppress markup, links, and notification references in model-authored text.
    plain = " ".join(text.split()).replace("@", "＠").replace(":", "꞉")
    return MARKUP.sub(lambda match: "\\" + match[0], plain)


def render(result: Review, threshold: int) -> str:
    score = "unavailable" if result.risk_score is None else str(result.risk_score)
    status = (
        "Human review requested"
        if (result.risk_score is None or result.risk_score >= threshold)
        else "Advisory review"
    )
    rows = [
        f"### MR Sentinel · {status}",
        f"Risk score: {score}",
        safe(result.summary),
        safe(result.rationale),
    ]
    rows.extend(
        f"- **{f.severity}** {safe(f.path)}:{f.line} · {safe(f.explanation)}"
        for f in result.findings
    )
    rows.extend(f"- Test gap: {safe(t)}" for t in result.missing_tests)
    return "\n\n".join(rows)


class GitLabClient:
    def __init__(self, client: httpx.AsyncClient, origin: str, project_id: int, token: str):
        self.client = client
        self.base = f"{origin.rstrip('/')}/api/v4/projects/{project_id}/merge_requests"
        self.headers = {"PRIVATE-TOKEN": token}

    async def diff(self, iid: int, limit: int) -> str:
        async with self.client.stream(
            "GET", f"{self.base}/{iid}/raw_diffs", headers=self.headers
        ) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=8192):
                body.extend(chunk)
                if len(body) > limit * 4:
                    raise ValueError("GitLab diff exceeds request budget")
        return body.decode("utf-8", errors="replace")

    async def post_note(self, iid: int, body: str) -> None:
        response = await self.client.post(
            f"{self.base}/{iid}/notes", headers=self.headers, data={"body": body}
        )
        response.raise_for_status()
