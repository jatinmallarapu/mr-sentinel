"""Schemas define the boundary between model suggestions and publishable evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["low", "medium", "high", "critical"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Finding(StrictModel):
    path: str = Field(min_length=1, max_length=300)
    line: int = Field(gt=0)
    severity: Severity
    explanation: str = Field(min_length=1, max_length=400)
    cwe: str | None = Field(default=None, pattern=r"^CWE-[0-9]+$")


class SecurityFindings(StrictModel):
    findings: list[Finding] = Field(max_length=12)


class TestAssessment(StrictModel):
    missing_tests: list[str] = Field(max_length=6)


class Summary(StrictModel):
    summary: str = Field(min_length=1, max_length=600)


class Judgment(StrictModel):
    risk_score: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=400)


class Review(StrictModel):
    status: Literal["complete", "degraded"]
    summary: str
    findings: list[Finding]
    missing_tests: list[str]
    risk_score: int | None
    rationale: str


class MergeEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    object_kind: Literal["merge_request"]
    project: "Project"
    object_attributes: "Attributes"


class Project(BaseModel):
    id: int = Field(gt=0)


class Attributes(BaseModel):
    iid: int = Field(gt=0)
    action: str
