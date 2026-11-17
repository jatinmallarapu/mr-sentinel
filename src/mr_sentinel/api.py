"""Expose local reviews and authenticated GitLab merge-request deliveries."""

import hmac
import os
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.responses import Response

from .config import load_settings
from .gitlab import GitLabClient, render
from .metrics import WEBHOOK_JOBS
from .orchestrator import review
from .providers.openai_compat import OpenAICompatProvider
from .schemas import MergeEvent, Review


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    async with httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as http:
        app.state.settings = settings
        app.state.provider = OpenAICompatProvider(
            http, str(settings.base_url), settings.model, os.environ.get("MODEL_API_KEY", "")
        )
        token = os.environ.get("GITLAB_API_TOKEN")
        project = os.environ.get("GITLAB_PROJECT_ID")
        app.state.project = int(project) if project else None
        app.state.gitlab = (
            GitLabClient(
                http, os.environ.get("GITLAB_URL", "https://gitlab.com"), int(project), token
            )
            if project and token
            else None
        )
        yield


app = FastAPI(title="MR Sentinel", lifespan=lifespan)


class LocalReview(BaseModel):
    diff: str = Field(min_length=1, max_length=100000)
    scanner_summary: str = Field(default="", max_length=4000)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/review", response_model=Review)
async def local_review(data: LocalReview, request: Request) -> Review:
    # Protect this endpoint at the ingress. It is meant for trusted local and bench clients.
    try:
        return await review(
            data.diff, data.scanner_summary, request.app.state.provider, request.app.state.settings
        )
    except ValueError:
        raise HTTPException(422, "Diff is empty or over budget") from None


async def process_event(state, iid: int) -> None:
    try:
        diff = await state.gitlab.diff(iid, state.settings.max_diff_chars)
        result = await review(diff, "", state.provider, state.settings)
        await state.gitlab.post_note(iid, render(result, state.settings.risk_threshold))
    except (httpx.HTTPError, ValueError):
        WEBHOOK_JOBS.labels("error").inc()
    else:
        WEBHOOK_JOBS.labels("posted").inc()


@app.post("/webhook/gitlab", status_code=202)
async def webhook(
    event: MergeEvent,
    request: Request,
    tasks: BackgroundTasks,
    gitlab_token: Annotated[str, Header(alias="X-Gitlab-Token")] = "",
) -> dict[str, str]:
    secret = os.environ.get("GITLAB_WEBHOOK_SECRET", "")
    if not secret or not hmac.compare_digest(secret.encode(), gitlab_token.encode()):
        raise HTTPException(401, "Webhook authentication failed")
    state = request.app.state
    if state.gitlab is None:
        raise HTTPException(503, "GitLab integration disabled")
    if event.project.id != state.project:
        raise HTTPException(403, "Unexpected project")
    if event.object_attributes.action not in {"open", "reopen", "update"}:
        return {"status": "ignored"}
    tasks.add_task(process_event, state, event.object_attributes.iid)
    return {"status": "accepted"}
