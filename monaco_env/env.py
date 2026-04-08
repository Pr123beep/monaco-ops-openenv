"""
MonacoOpsEnv — OpenEnv-compliant environment.

step(action)  → Observation, Reward, done, info
reset()       → Observation
state()       → dict
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .graders import grade_file_apis, grade_full_editor, grade_settings_api
from .models import Action, FileContent, Observation, Reward, TestResult

# Path to the TypeScript workspace (overridable via env-var for Docker)
WORKSPACE_DIR: str = os.environ.get(
    "MONACO_WORKSPACE",
    str(Path(__file__).resolve().parent.parent / "environment"),
)

# Files the agent can read as context
WATCHED_FILES = [
    "src/node/server.ts",
    "src/app/main.ts",
    "src/shared/autocorrect.ts",
    "src/shared/contracts.ts",
    "package.json",
    "data/settings.json",
]

TASKS: Dict[str, Dict[str, Any]] = {
    "settings-api": {
        "description": (
            "Implement GET /api/settings and PUT /api/settings in src/node/server.ts. "
            "Settings must be read from and persisted to data/settings.json on every PUT."
        ),
        "grader": grade_settings_api,
        "max_steps": 10,
        "checks": ["get_keys", "put_ok", "get_after_put", "disk_write"],
    },
    "file-api": {
        "description": (
            "Implement GET /api/files, POST /api/files/open, and POST /api/files/save "
            "in src/node/server.ts. Restrict all file ops to data/workspace/ and reject "
            "path traversal (../) with a 4xx response."
        ),
        "grader": grade_file_apis,
        "max_steps": 15,
        "checks": ["list_files", "open_file", "save_file", "round_trip", "traversal_blocked"],
    },
    "full-editor": {
        "description": (
            "Implement the complete Monaco editor: settings API, file APIs, AI completion "
            "proxy (POST /api/ai/complete), Monaco npm package with bundled workers, "
            "multi-file tab strip with role=tablist, and autocorrect module."
        ),
        "grader": grade_full_editor,
        "max_steps": 25,
        "checks": [
            "settings_api", "file_api", "ai_proxy", "monaco_pkg",
            "worker_assets", "tablist", "autocorrect", "build_clean",
        ],
    },
}

# Allowed write paths (agent cannot write outside these)
SAFE_WRITE_PREFIXES = ("src/", "data/", "public/", "package.json")
# Allowed run commands
ALLOWED_COMMANDS = ("npm run build", "npm install", "npm ci")


def _read_watched_files() -> List[FileContent]:
    results = []
    for rel in WATCHED_FILES:
        full = os.path.join(WORKSPACE_DIR, rel)
        if os.path.exists(full):
            with open(full, encoding="utf-8", errors="replace") as f:
                content = f.read()
            results.append(FileContent(path=rel, content=content))
    return results


class MonacoOpsEnv:
    """OpenEnv-compliant environment for the Monaco Ops code-editing task."""

    def __init__(self, task_id: str = "settings-api"):
        if task_id not in TASKS:
            raise ValueError(
                f"Unknown task_id {task_id!r}. Choose from: {list(TASKS)}"
            )
        self.task_id = task_id
        self.task = TASKS[task_id]
        self._step: int = 0
        self._done: bool = False
        self._last_scores: Dict[str, float] = {}
        self._prev_total: float = 0.0

    # ── OpenEnv API ───────────────────────────────────────────────────────────

    def reset(self) -> Observation:
        """Reset episode state and return initial observation."""
        self._step = 0
        self._done = False
        self._last_scores = {}
        self._prev_total = 0.0
        return self._observation(
            output=f"New episode started. Task: {self.task['description']}",
            success=True,
        )

    def step(self, action: Action) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        """Execute one action and return (observation, reward, done, info)."""
        if self._done:
            obs = self._observation("Episode already finished.", False)
            return obs, Reward(value=0.0, breakdown={}, done=True), True, {}

        self._step += 1
        output, success = self._execute(action)

        # Run grader
        try:
            scores = self.task["grader"](WORKSPACE_DIR)
        except Exception as exc:
            scores = {k: 0.0 for k in self.task["checks"]}
            output += f"\n[grader error] {exc}"

        total = round(sum(scores.values()), 4)

        # Shaped reward: reward delta in progress + small step penalty
        delta = max(0.0, total - self._prev_total)
        step_reward = round(delta - 0.01, 4)   # -0.01 per step to discourage stalling
        step_reward = max(0.0, step_reward)

        self._last_scores = scores
        self._prev_total = max(self._prev_total, total)

        done = total >= 0.95 or self._step >= self.task["max_steps"]
        self._done = done

        reward = Reward(
            value=total,
            breakdown=scores,
            done=done,
            info={"step_reward": step_reward, "delta": delta},
        )
        obs = self._observation(output, success, scores)
        return obs, reward, done, {"scores": scores, "total": total}

    def state(self) -> Dict[str, Any]:
        """Return current episode state (non-observation metadata)."""
        return {
            "task_id": self.task_id,
            "step": self._step,
            "done": self._done,
            "last_scores": self._last_scores,
            "best_total": self._prev_total,
            "workspace": WORKSPACE_DIR,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _execute(self, action: Action) -> Tuple[str, bool]:
        try:
            if action.action_type == "write_file":
                return self._write_file(action)
            elif action.action_type == "run_command":
                return self._run_command(action)
            else:
                return f"Unknown action_type: {action.action_type!r}", False
        except Exception as exc:
            return f"Action raised: {exc}", False

    def _write_file(self, action: Action) -> Tuple[str, bool]:
        if not action.file_path or action.file_content is None:
            return "write_file requires both file_path and file_content", False
        # Security: only allow writes inside safe prefixes
        if not any(action.file_path.startswith(p) for p in SAFE_WRITE_PREFIXES):
            return (
                f"Blocked: file_path must start with one of {SAFE_WRITE_PREFIXES}",
                False,
            )
        # Security: block path traversal
        if ".." in action.file_path:
            return "Blocked: path traversal not allowed", False

        full = os.path.join(WORKSPACE_DIR, action.file_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(action.file_content)
        return (
            f"Wrote {action.file_path} ({len(action.file_content):,} chars)",
            True,
        )

    def _run_command(self, action: Action) -> Tuple[str, bool]:
        cmd = (action.command or "").strip()
        if not any(cmd.startswith(a) for a in ALLOWED_COMMANDS):
            return f"Blocked: only {ALLOWED_COMMANDS} are permitted", False
        result = subprocess.run(
            cmd.split(),
            cwd=WORKSPACE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        combined = (result.stdout + result.stderr)[-3000:]
        return combined or "(no output)", result.returncode == 0

    def _observation(
        self,
        output: str,
        success: bool,
        scores: Dict[str, float] | None = None,
    ) -> Observation:
        test_results = []
        if scores:
            for name, val in scores.items():
                test_results.append(
                    TestResult(name=name, passed=val > 0.05, message=f"{val:.3f}")
                )
        return Observation(
            task_id=self.task_id,
            step=self._step,
            files=_read_watched_files(),
            test_results=test_results,
            last_action_output=output[:2000],
            last_action_success=success,
            score_so_far=round(sum((scores or {}).values()), 4),
        )
