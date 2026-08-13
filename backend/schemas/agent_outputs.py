from pydantic import BaseModel, Field
from typing import Literal


class FileChange(BaseModel):
    filename: str
    change_type: Literal["added", "modified", "deleted"]
    summary: str = Field(description="1-2 sentence summary of what changed")
    key_functions: list[str] = Field(default_factory=list)


class CodeReaderOutput(BaseModel):
    files_changed: list[FileChange]
    overall_summary: str
    language: str
    complexity_estimate: Literal["low", "medium", "high"]


class BugFinding(BaseModel):
    severity: Literal["critical", "warning", "suggestion"]
    filename: str
    line_hint: str
    description: str
    fix_suggestion: str


class BugDetectorOutput(BaseModel):
    findings: list[BugFinding]
    overall_risk_score: float = Field(ge=0.0, le=10.0)


class TestCase(BaseModel):
    function_name: str
    test_description: str
    pytest_stub: str


class TestSuggesterOutput(BaseModel):
    suggested_tests: list[TestCase]
    coverage_gaps: list[str]


class DocImprovement(BaseModel):
    filename: str
    function_name: str
    current_doc: str
    improved_doc: str


class DocWriterOutput(BaseModel):
    improvements: list[DocImprovement]
    missing_docs_count: int
