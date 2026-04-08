"""
Monaco Ops OpenEnv — Baseline Inference Script

Runs a language model against all 3 tasks and emits structured logs.

Log format (required by competition):
  [START] task=<task_id> env=monaco-ops model=<MODEL_NAME>
  [STEP]  step=<n> action=<label> reward=<r> done=<bool> error=<msg|null>
  [END]   success=<bool> steps=<n> score=<s> rewards=<r1,r2,...>

Usage:
  export HF_TOKEN=hf_...
  export API_BASE_URL=https://router.huggingface.co/v1
  export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
  python inference.py
"""

from __future__ import annotations

import json
import os
import textwrap
from typing import Dict, List, Optional

from openai import OpenAI

from monaco_env.env import MonacoOpsEnv, TASKS
from monaco_env.models import Action

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY: str = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or ""
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_FILTER: str = os.getenv("MONACO_TASK", "all")   # "all" or a single task id

MAX_STEPS = 12
TEMPERATURE = 0.15
MAX_TOKENS = 3000
SUCCESS_THRESHOLD = 0.75


# ── Logging ───────────────────────────────────────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    err = error if error else "null"
    done_str = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f}"
        f" done={done_str} error={err}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps}"
        f" score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ── Prompts ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert TypeScript / Node.js engineer completing a Monaco code editor.

The workspace is a Node.js project (`type: "module"`, TypeScript 5, ESM).
The main server file is `src/node/server.ts`.

You respond with exactly ONE JSON action object — no markdown, no explanation.

Allowed action shapes:

1) Write a file (always write COMPLETE file content, never diffs):
{"action_type": "write_file", "file_path": "src/node/server.ts", "file_content": "..."}

2) Run a build (do this after writing files):
{"action_type": "run_command", "command": "npm run build"}

Strategy:
- First write the full implementation of src/node/server.ts.
- Then run npm run build.
- If tests still fail, fix and rebuild.
- For the hard task you also need to update package.json (add monaco-editor)
  and update src/app/main.ts with a tablist and Monaco integration.
""").strip()


def _build_user_prompt(obs, task_desc: str, history: List[Dict]) -> str:
    tests_block = "\n".join(
        f"  {'✅' if t.passed else '❌'} {t.name}: {t.message}"
        for t in obs.test_results
    ) or "  (no tests run yet)"

    # Include key file contents
    file_blocks = []
    for fc in obs.files:
        preview = fc.content[:4000] if len(fc.content) > 4000 else fc.content
        file_blocks.append(f"### {fc.path}\n```typescript\n{preview}\n```")
    files_section = "\n\n".join(file_blocks)

    return textwrap.dedent(f"""
        TASK: {task_desc}
        Step {obs.step} | Score so far: {obs.score_so_far:.3f}

        TEST RESULTS:
        {tests_block}

        LAST ACTION OUTPUT (truncated):
        {obs.last_action_output[:600]}

        WORKSPACE FILES:
        {files_section}

        Output your next JSON action now.
    """).strip()


# ── Agent loop ────────────────────────────────────────────────────────────────

def get_action(
    client: OpenAI,
    obs,
    task_desc: str,
    history: List[Dict],
) -> tuple[Optional[Action], Optional[str]]:
    """Call the LLM and parse the response into an Action."""
    user_msg = _build_user_prompt(obs, task_desc, history)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Keep last 4 turns of history to stay within context
    messages.extend(history[-4:])
    messages.append({"role": "user", "content": user_msg})

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    raw = response.choices[0].message.content or ""
    history.append({"role": "assistant", "content": raw})

    # Strip markdown fences if the model added them
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) >= 2 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        return Action(**data), None
    except Exception as exc:
        return None, f"json_parse_error: {exc}"


def run_task(client: OpenAI, task_id: str) -> float:
    env = MonacoOpsEnv(task_id=task_id)
    task_desc = env.task["description"]

    log_start(task_id, "monaco-ops", MODEL_NAME)
    obs = env.reset()

    rewards: List[float] = []
    history: List[Dict] = []
    final_score = 0.0
    error_streak = 0

    for step_num in range(1, MAX_STEPS + 1):
        action, parse_err = get_action(client, obs, task_desc, history)

        if action is None:
            error_streak += 1
            log_step(step_num, "parse_error", 0.0, False, parse_err)
            rewards.append(0.0)
            if error_streak >= 3:
                break
            continue

        error_streak = 0
        action_label = (
            f"write_file('{action.file_path}')"
            if action.action_type == "write_file"
            else f"run_command('{action.command}')"
        )

        obs, reward, done, info = env.step(action)
        final_score = reward.value
        rewards.append(final_score)

        log_step(step_num, action_label, final_score, done, None)

        if done:
            break

    success = final_score >= SUCCESS_THRESHOLD
    log_end(success, len(rewards), final_score, rewards)
    return final_score


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not API_KEY:
        raise EnvironmentError(
            "Set HF_TOKEN or API_KEY environment variable before running inference.py"
        )

    client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

    task_ids = list(TASKS.keys()) if TASK_FILTER == "all" else [TASK_FILTER]
    all_scores: Dict[str, float] = {}

    for task_id in task_ids:
        score = run_task(client, task_id)
        all_scores[task_id] = score
        print(flush=True)  # blank line between tasks

    print("=== FINAL SCORES ===", flush=True)
    for task_id, score in all_scores.items():
        print(f"  {task_id}: {score:.3f}", flush=True)
    avg = sum(all_scores.values()) / max(len(all_scores), 1)
    print(f"  average: {avg:.3f}", flush=True)


if __name__ == "__main__":
    main()
