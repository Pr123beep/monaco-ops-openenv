"""
FastAPI wrapper that exposes the MonacoOpsEnv over HTTP.
This is what the HF Space serves; it satisfies the OpenEnv HTTP spec.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from monaco_env.env import MonacoOpsEnv, TASKS
from monaco_env.models import Action

app = FastAPI(
    title="Monaco Ops OpenEnv",
    description=(
        "OpenEnv environment: AI agent implements a Monaco code editor "
        "from a TypeScript scaffold."
    ),
    version="1.0.0",
)

# One env instance per task_id, created lazily
_envs: Dict[str, MonacoOpsEnv] = {}


def _env(task_id: str) -> MonacoOpsEnv:
    if task_id not in TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id {task_id!r}. Valid: {list(TASKS)}",
        )
    if task_id not in _envs:
        _envs[task_id] = MonacoOpsEnv(task_id=task_id)
    return _envs[task_id]


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "env": "monaco-ops", "tasks": list(TASKS)}


@app.get("/tasks")
def list_tasks() -> Any:
    return [
        {
            "id": tid,
            "description": t["description"],
            "max_steps": t["max_steps"],
            "checks": t["checks"],
        }
        for tid, t in TASKS.items()
    ]


@app.post("/reset")
def reset(task_id: str = Query(default="settings-api")) -> Any:
    env = _env(task_id)
    obs = env.reset()
    return obs.model_dump()


@app.post("/step")
def step(
    action: Action,
    task_id: str = Query(default="settings-api"),
) -> Any:
    env = _env(task_id)
    obs, reward, done, info = env.step(action)
    return {
        "observation": obs.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/state")
def state(task_id: str = Query(default="settings-api")) -> Any:
    env = _env(task_id)
    return env.state()
