"""Verify that a webhook cannot select another project or bypass authentication."""

import pytest
from fastapi.testclient import TestClient

from mr_sentinel.api import app
from mr_sentinel.demo import SAMPLE, FixtureProvider

EVENT = {
    "object_kind": "merge_request",
    "project": {"id": 42},
    "object_attributes": {"iid": 9, "action": "open"},
}


class FakeGitLab:
    def __init__(self):
        self.notes = []

    async def diff(self, iid, limit):
        assert iid == 9
        return SAMPLE

    async def post_note(self, iid, body):
        self.notes.append((iid, body))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITLAB_WEBHOOK_SECRET", "fixture")
    with TestClient(app) as session:
        app.state.project = 42
        app.state.gitlab = FakeGitLab()
        app.state.provider = FixtureProvider()
        yield session


def test_authentication_and_project_boundary(client):
    assert client.post("/webhook/gitlab", json=EVENT).status_code == 401
    assert (
        client.post(
            "/webhook/gitlab",
            json={**EVENT, "project": {"id": 41}},
            headers={"X-Gitlab-Token": "fixture"},
        ).status_code
        == 403
    )
    assert not app.state.gitlab.notes


def test_one_note_is_rendered_per_accepted_delivery(client):
    response = client.post("/webhook/gitlab", json=EVENT, headers={"X-Gitlab-Token": "fixture"})
    assert response.status_code == 202
    [(iid, body)] = app.state.gitlab.notes
    assert iid == 9 and "Risk score: 70" in body


def test_ignored_action_and_endpoints(client):
    event = {**EVENT, "object_attributes": {"iid": 9, "action": "close"}}
    assert client.post(
        "/webhook/gitlab", json=event, headers={"X-Gitlab-Token": "fixture"}
    ).json() == {"status": "ignored"}
    assert client.get("/health").json()["status"] == "alive"
    assert "review_latency_seconds" in client.get("/metrics").text
    assert client.post("/review", json={"diff": " "}).status_code == 422
    assert client.post("/review", json={"diff": SAMPLE}).status_code == 200
