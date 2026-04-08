"""
Task graders for Monaco Ops.

Each grader:
  1. Runs `npm run build` inside workspace_dir
  2. Starts the compiled Node server on a free port
  3. Hits HTTP endpoints to verify behaviour
  4. Returns a dict[check_name -> float] where each value is in [0.0, max_weight]
     and the weights for a task sum to 1.0
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Tuple
from urllib import error, request


# ── Helpers ───────────────────────────────────────────────────────────────────

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _http(method: str, url: str, payload: dict | None = None) -> Tuple[int, dict]:
    headers = {"content-type": "application/json"} if payload is not None else {}
    data = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(url, method=method, headers=headers, data=data)
    try:
        with request.urlopen(req, timeout=6) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except error.HTTPError as exc:
        body = exc.read()
        return exc.code, (json.loads(body) if body else {})
    except Exception:
        return 0, {}


def _wait_for(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with request.urlopen(url, timeout=1):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def _npm_build(workspace: str) -> bool:
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=workspace,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return result.returncode == 0


def _start_server(workspace: str) -> Tuple[subprocess.Popen | None, int]:
    port = _free_port()
    env = os.environ.copy()
    env["PORT"] = str(port)
    server_js = os.path.join(workspace, "dist", "node", "server.js")
    if not os.path.exists(server_js):
        return None, port
    proc = subprocess.Popen(
        ["node", server_js],
        cwd=workspace,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not _wait_for(f"http://127.0.0.1:{port}/health", timeout=20):
        proc.terminate()
        return None, port
    return proc, port


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


# ── Task 1 — Settings API (Easy) ─────────────────────────────────────────────
# Weights: get_keys=0.25  put_ok=0.25  get_after_put=0.25  disk_write=0.25

def grade_settings_api(workspace: str) -> Dict[str, float]:
    scores: Dict[str, float] = {
        "get_keys": 0.0,
        "put_ok": 0.0,
        "get_after_put": 0.0,
        "disk_write": 0.0,
    }
    if not _npm_build(workspace):
        return scores

    proc, port = _start_server(workspace)
    base = f"http://127.0.0.1:{port}"
    try:
        status, body = _http("GET", f"{base}/api/settings")
        if status == 200:
            required = ["theme", "smoothTyping", "autoCorrect", "apiKey", "apiBaseUrl"]
            if all(k in body for k in required):
                scores["get_keys"] = 0.25

        new_settings = {
            "theme": "light",
            "smoothTyping": False,
            "autoCorrect": True,
            "apiKey": "grader-test",
            "apiBaseUrl": "http://grader.local",
        }
        status2, _ = _http("PUT", f"{base}/api/settings", new_settings)
        if status2 == 200:
            scores["put_ok"] = 0.25

        _, re_read = _http("GET", f"{base}/api/settings")
        if re_read.get("theme") == "light" and re_read.get("apiKey") == "grader-test":
            scores["get_after_put"] = 0.25

        disk_path = os.path.join(workspace, "data", "settings.json")
        if os.path.exists(disk_path):
            with open(disk_path, encoding="utf-8") as f:
                disk = json.load(f)
            if disk.get("theme") == "light" and disk.get("apiKey") == "grader-test":
                scores["disk_write"] = 0.25
    finally:
        _stop(proc)
    return scores


# ── Task 2 — File APIs (Medium) ───────────────────────────────────────────────
# Weights: list=0.20  open=0.20  save=0.20  round_trip=0.20  traversal=0.20

def grade_file_apis(workspace: str) -> Dict[str, float]:
    scores: Dict[str, float] = {
        "list_files": 0.0,
        "open_file": 0.0,
        "save_file": 0.0,
        "round_trip": 0.0,
        "traversal_blocked": 0.0,
    }
    if not _npm_build(workspace):
        return scores

    proc, port = _start_server(workspace)
    base = f"http://127.0.0.1:{port}"
    try:
        status, files = _http("GET", f"{base}/api/files")
        if status == 200 and isinstance(files, list):
            if any(isinstance(f, dict) and f.get("path") == "welcome.ts" for f in files):
                scores["list_files"] = 0.20

        status, opened = _http("POST", f"{base}/api/files/open", {"path": "welcome.ts"})
        if status == 200 and "content" in opened and opened.get("path") == "welcome.ts":
            scores["open_file"] = 0.20

        test_content = "# written by grader\nresult = 42\n"
        status, _ = _http("POST", f"{base}/api/files/save",
                           {"path": "grader_test.py", "content": test_content})
        saved_path = os.path.join(workspace, "data", "workspace", "grader_test.py")
        if os.path.exists(saved_path):
            scores["save_file"] = 0.20

        status, re_opened = _http("POST", f"{base}/api/files/open", {"path": "grader_test.py"})
        if status == 200 and re_opened.get("content") == test_content:
            scores["round_trip"] = 0.20

        status, _ = _http("POST", f"{base}/api/files/open", {"path": "../../../etc/passwd"})
        if 400 <= status < 500:
            scores["traversal_blocked"] = 0.20
    finally:
        _stop(proc)
    return scores


# ── Task 3 — Full Monaco Editor (Hard) ────────────────────────────────────────
# Weights: settings=0.12  files=0.12  ai_proxy=0.18  monaco_pkg=0.14
#          workers=0.14  tablist=0.12  autocorrect=0.10  build_clean=0.08

def grade_full_editor(workspace: str) -> Dict[str, float]:
    weights = {
        "settings_api":  0.12,
        "file_api":      0.12,
        "ai_proxy":      0.18,
        "monaco_pkg":    0.14,
        "worker_assets": 0.14,
        "tablist":       0.12,
        "autocorrect":   0.10,
        "build_clean":   0.08,
    }
    scores: Dict[str, float] = {k: 0.0 for k in weights}

    # --- build_clean ---
    build_ok = _npm_build(workspace)
    if build_ok:
        scores["build_clean"] = weights["build_clean"]
    else:
        return scores  # nothing else can pass without a build

    # --- monaco_pkg ---
    pkg_path = os.path.join(workspace, "package.json")
    try:
        with open(pkg_path, encoding="utf-8") as f:
            pkg = json.load(f)
        all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        if "monaco-editor" in all_deps or "@monaco-editor/react" in all_deps:
            scores["monaco_pkg"] = weights["monaco_pkg"]
    except Exception:
        pass

    # --- worker_assets ---
    dist_dir = os.path.join(workspace, "dist")
    if os.path.isdir(dist_dir):
        all_files = []
        for root, _, fnames in os.walk(dist_dir):
            all_files.extend(fnames)
        if any("worker" in name.lower() for name in all_files):
            scores["worker_assets"] = weights["worker_assets"]

    # --- tablist ---
    main_ts = os.path.join(workspace, "src", "app", "main.ts")
    if os.path.exists(main_ts):
        with open(main_ts, encoding="utf-8") as f:
            src = f.read()
        if "tablist" in src:
            scores["tablist"] = weights["tablist"]

    # --- autocorrect ---
    script = (
        "import { applyAutocorrect } from './dist/shared/autocorrect.js';"
        "process.stdout.write(applyAutocorrect('funtion demo() { retrun teh value; }'));"
    )
    ac = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=workspace, capture_output=True, text=True, timeout=15,
    )
    if ac.stdout.strip() == "function demo() { return the value; }":
        scores["autocorrect"] = weights["autocorrect"]

    # --- runtime checks ---
    proc, port = _start_server(workspace)
    base = f"http://127.0.0.1:{port}"
    try:
        # settings sub-score
        s_scores = grade_settings_api(workspace)
        s_total = sum(s_scores.values())
        scores["settings_api"] = weights["settings_api"] * s_total  # s_total in [0,1]

        # file sub-score
        f_scores = grade_file_apis(workspace)
        f_total = sum(f_scores.values())
        scores["file_api"] = weights["file_api"] * f_total

        # ai_proxy
        captured: Dict = {}

        class _MockHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("content-length", "0"))
                captured["auth"] = self.headers.get("authorization", "")
                captured["body"] = json.loads(self.rfile.read(length) or b"{}")
                captured["path"] = self.path
                resp = json.dumps({
                    "choices": [{"message": {"content": "mock completion"}}]
                }).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, *_):
                pass

        mock_srv = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
        mock_thread = threading.Thread(target=mock_srv.serve_forever, daemon=True)
        mock_thread.start()
        mock_base = f"http://127.0.0.1:{mock_srv.server_address[1]}"

        try:
            _http("PUT", f"{base}/api/settings", {
                "theme": "dark", "smoothTyping": True, "autoCorrect": True,
                "apiKey": "mock-key-123", "apiBaseUrl": mock_base,
            })
            ai_status, ai_resp = _http("POST", f"{base}/api/ai/complete", {
                "instruction": "Add a log statement",
                "content": "const x = 1;",
                "path": "welcome.ts",
            })
            ai_ok = (
                ai_status == 200
                and "completion" in ai_resp
                and captured.get("auth") == "Bearer mock-key-123"
                and "/v1/chat/completions" in captured.get("path", "")
            )
            if ai_ok:
                scores["ai_proxy"] = weights["ai_proxy"]

            # verify 4xx when apiKey is empty
            _http("PUT", f"{base}/api/settings", {
                "theme": "dark", "smoothTyping": True, "autoCorrect": True,
                "apiKey": "", "apiBaseUrl": mock_base,
            })
            no_key_status, _ = _http("POST", f"{base}/api/ai/complete", {
                "instruction": "still try", "content": "x", "path": "f.ts",
            })
            if 400 <= no_key_status < 500 and ai_ok:
                scores["ai_proxy"] = weights["ai_proxy"]  # already set, just confirm
        finally:
            mock_srv.shutdown()
            mock_thread.join(timeout=5)
    finally:
        _stop(proc)

    return scores
