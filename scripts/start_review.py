"""Run the real console on one port; no demo records or private files required."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init", action="store_true", help="Create .env once, then exit")
    parser.add_argument("--build", action="store_true", help="Install/build Vue before starting")
    parser.add_argument("--with-cv", action="store_true", help="Start and enroll a local CV node")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.init:
        from cryptography.fernet import Fernet
        template = (ROOT / ".env.review.example").read_text(encoding="utf-8")
        template = template.replace("GENERATE_INTERNAL_TOKEN", secrets.token_urlsafe(32))
        template = template.replace("GENERATE_CV_TOKEN", secrets.token_urlsafe(32))
        template = template.replace("GENERATE_ENCRYPTION_KEY", Fernet.generate_key().decode())
        # Exclusive creation protects an existing configuration, including its credentials.
        with (ROOT / ".env").open("x", encoding="utf-8") as output:
            output.write(template)
        print("Created .env. Set AGENT_LLM_API_KEY locally before starting.")
        return

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    from agent.core.config import Settings
    settings = Settings.from_env()
    settings.validate_for_runtime()
    host, port = settings.bind_host, settings.port
    if host != "127.0.0.1":
        raise RuntimeError("Review launcher requires AGENT_BIND_HOST=127.0.0.1")
    cv_port = int(os.getenv("CV_CONTROL_PORT", "8100"))
    for candidate in ([port, cv_port] if args.with_cv else [port]):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", candidate))
    if args.with_cv:
        if not (ROOT / "perception/weights/helmet_head_person_s.pt").is_file():
            raise RuntimeError("Place the trained detector at perception/weights/helmet_head_person_s.pt")
        if not os.getenv("CV_NODE_TOKEN") or not os.getenv("CV_NODE_ID"):
            raise RuntimeError("CV_NODE_ID and CV_NODE_TOKEN are required")
    for directory in ("runs", "runs/media/snapshots", "runs/input/videos", "knowledge/standard", "knowledge/accident_reports"):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)
    if args.build:
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not npm:
            raise RuntimeError("Install Node.js and npm first")
        env = dict(os.environ, VITE_API_BASE_URL="", VITE_USE_MOCK="false", VITE_LOCAL_VIDEO_DEMO="false")
        subprocess.run([npm, "ci"], cwd=ROOT / "web", env=env, check=True)
        subprocess.run([npm, "run", "build"], cwd=ROOT / "web", env=env, check=True)
    if not (ROOT / "web/dist/index.html").is_file():
        raise RuntimeError("Build the frontend first: python -m scripts.start_review --build")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    children: list[subprocess.Popen] = []
    opener = build_opener(ProxyHandler({}))
    agent_url = f"http://127.0.0.1:{port}"

    def wait_ready(url: str, child: subprocess.Popen, headers: dict | None = None) -> None:
        for _ in range(90):
            if child.poll() is not None:
                raise RuntimeError("Server exited before readiness; see console output")
            try:
                with opener.open(Request(url, headers=headers or {}), timeout=2) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError):
                pass
            time.sleep(1)
        raise RuntimeError("Server readiness timed out; see console output")

    try:
        children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "scripts.serve_demo:create_demo_app", "--factory", "--host", host, "--port", str(port)]))
        wait_ready(agent_url + "/docs", children[0])
        if args.with_cv:
            control_url = f"http://127.0.0.1:{cv_port}"
            payload = {"node_id": os.environ["CV_NODE_ID"], "display_name": "本地评审 CV 节点", "control_url": control_url, "capacity": int(os.getenv("CV_NODE_CAPACITY", "2")), "control_token": os.environ["CV_NODE_TOKEN"]}
            request = Request(agent_url + "/api/v1/cv-nodes", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            try:
                with opener.open(request, timeout=15):
                    pass
            except HTTPError as exc:
                if exc.code != 409:
                    raise RuntimeError(f"CV enrollment failed (HTTP {exc.code})") from None
                # No update or credential replacement for an existing node.
                print("CV node already registered; checking the configured token when starting.")
            env = dict(os.environ, AGENT_URL=agent_url)
            children.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "perception.control_api:create_control_app", "--factory", "--host", "127.0.0.1", "--port", str(cv_port)], env=env))
            wait_ready(control_url + "/control/v1/health", children[-1], {"Authorization": "Bearer " + os.environ["CV_NODE_TOKEN"]})
        print(f"Open {agent_url}/dashboard ; Ctrl+C stops only servers started by this command.")
        while all(child.poll() is None for child in children):
            time.sleep(1)
        raise RuntimeError("A server exited; see console output")
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    main()
