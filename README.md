---
title: Monaco Ops OpenEnv
emoji: 🖊️
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
tags:
  - openenv
  - reinforcement-learning
  - code-generation
  - typescript
  - software-engineering
---

# Monaco Ops — OpenEnv Environment

An [OpenEnv](https://github.com/huggingface/openenv) environment where an AI agent
must implement a **Monaco-powered TypeScript code editor** from a partial scaffold.
The agent writes TypeScript source files; graders evaluate correctness by compiling
the project and hitting its HTTP endpoints.

## Why this environment?

Code editing and implementation is a core real-world task for AI agents.
Unlike toy environments, this one requires the agent to write syntactically correct
TypeScript, understand HTTP server design patterns, and pass end-to-end integration
tests — skills that directly transfer to production software engineering.

---

## Action Space

```json
// Write a file (always complete content, never diffs)
{"action_type": "write_file", "file_path": "src/node/server.ts", "file_content": "..."}

// Run an npm command
{"action_type": "run_command", "command": "npm run build"}
```

Allowed `file_path` prefixes: `src/`, `data/`, `public/`, `package.json`  
Allowed commands: `npm run build`, `npm install`, `npm ci`

## Observation Space

```json
{
  "task_id": "settings-api",
  "step": 3,
  "files": [
    {"path": "src/node/server.ts", "content": "..."},
    {"path": "package.json", "content": "..."}
  ],
  "test_results": [
    {"name": "get_keys",   "passed": true,  "message": "0.250"},
    {"name": "put_ok",     "passed": false, "message": "0.000"}
  ],
  "last_action_output": "error TS2304: Cannot find name 'readFile'...",
  "last_action_success": false,
  "score_so_far": 0.25
}
```

---

## Tasks

### Task 1 — `settings-api` (Easy, max 10 steps)

Implement `GET /api/settings` and `PUT /api/settings` in `src/node/server.ts`.
Settings must be read from and written back to `data/settings.json`.

| Check | Weight |
|---|---|
| GET /api/settings returns all 5 keys | 0.25 |
| PUT /api/settings returns 200 | 0.25 |
| GET after PUT reflects new values | 0.25 |
| data/settings.json updated on disk | 0.25 |

### Task 2 — `file-api` (Medium, max 15 steps)

Implement workspace file APIs: list, open, save. Path traversal must be blocked.

| Check | Weight |
|---|---|
| GET /api/files includes welcome.ts | 0.20 |
| POST /api/files/open returns content | 0.20 |
| POST /api/files/save creates file on disk | 0.20 |
| Save → open round-trip is lossless | 0.20 |
| `../` path traversal rejected with 4xx | 0.20 |

### Task 3 — `full-editor` (Hard, max 25 steps)

Implement everything: settings, files, AI proxy, Monaco npm package,
bundled workers, tablist UI, and shared autocorrect module.

| Check | Weight |
|---|---|
| settings_api passes | 0.12 |
| file_api passes | 0.12 |
| POST /api/ai/complete proxies correctly | 0.18 |
| monaco-editor in package.json | 0.14 |
| Worker assets present in dist/ | 0.14 |
| `role="tablist"` in src/app/main.ts | 0.12 |
| Shared autocorrect module works post-build | 0.10 |
| npm run build exits 0 | 0.08 |

---

## Reward Function

- **`reward.value`** — normalised total score `[0.0, 1.0]`
- Partial progress is rewarded at every step (delta from previous best score)
- Small step penalty (`-0.01`) discourages stalling
- Episode ends when score ≥ 0.95 or `max_steps` reached

---

## HTTP API (HF Space)

```
GET  /health            → {"ok": true, "tasks": [...]}
GET  /tasks             → list of task metadata
POST /reset?task_id=... → initial Observation
POST /step?task_id=...  → {observation, reward, done, info}
GET  /state?task_id=... → episode state dict
```

---

## Setup & Usage

### Local (Python)

```bash
git clone https://huggingface.co/spaces/<your-space>
cd monaco-ops-openenv
pip install -r requirements.txt
cd environment && npm ci && cd ..
uvicorn api:app --port 7860
```

### Docker

```bash
docker build -t monaco-ops .
docker run -p 7860:7860 \
  -e HF_TOKEN=hf_... \
  -e API_BASE_URL=https://router.huggingface.co/v1 \
  -e MODEL_NAME=Qwen/Qwen2.5-72B-Instruct \
  monaco-ops
```

### Run inference

```bash
export HF_TOKEN=hf_...
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
python inference.py
```

---

## Baseline Scores

Model: `Qwen/Qwen2.5-72B-Instruct`

| Task | Score |
|---|---|
| settings-api | ~0.75 |
| file-api | ~0.60 |
| full-editor | ~0.30 |

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `HF_TOKEN` | Yes (inference) | HuggingFace / API key |
| `API_BASE_URL` | Yes (inference) | LLM API base URL |
| `MODEL_NAME` | Yes (inference) | Model identifier |
| `MONACO_WORKSPACE` | No | Path to TS workspace (default: `./environment`) |
| `MONACO_TASK` | No | Single task to run (`all` = run all three) |
