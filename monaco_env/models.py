from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FileContent(BaseModel):
    path: str
    content: str


class TestResult(BaseModel):
    name: str
    passed: bool
    message: str


class Observation(BaseModel):
    """Typed observation returned by step() and reset()."""
    task_id: str
    step: int
    files: List[FileContent] = Field(
        description="Current contents of key workspace files"
    )
    test_results: List[TestResult] = Field(
        default_factory=list,
        description="Per-check pass/fail from the last grader run"
    )
    last_action_output: str = Field(
        description="stdout/stderr of the last action (truncated to 2000 chars)"
    )
    last_action_success: bool
    score_so_far: float = Field(
        ge=0.0, le=1.0,
        description="Normalised total score from the last grader run"
    )


class Action(BaseModel):
    """Typed action consumed by step()."""
    action_type: str = Field(
        description="'write_file' or 'run_command'"
    )
    # write_file fields
    file_path: Optional[str] = Field(
        default=None,
        description="Relative path inside the workspace, e.g. src/node/server.ts"
    )
    file_content: Optional[str] = Field(
        default=None,
        description="Complete new content of the file"
    )
    # run_command fields
    command: Optional[str] = Field(
        default=None,
        description="npm run build | npm install | npm ci"
    )


class Reward(BaseModel):
    """Typed reward returned by step()."""
    value: float = Field(ge=0.0, le=1.0, description="Normalised episode score")
    breakdown: Dict[str, float] = Field(
        description="Per-check scores that sum to value"
    )
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)
