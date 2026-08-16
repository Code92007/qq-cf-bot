#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import smtplib
import socket
import subprocess
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Tuple


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    _load_dotenv(ROOT_DIR / ".env")
    if not _bool_env("NAPCAT_WATCHDOG_ENABLED", False):
        print("NapCat watchdog disabled. Set NAPCAT_WATCHDOG_ENABLED=true to enable it.", flush=True)
        return

    interval = max(10, _int_env("NAPCAT_WATCHDOG_INTERVAL_SECONDS", 60))
    cooldown = max(interval, _int_env("NAPCAT_WATCHDOG_RESTART_COOLDOWN_SECONDS", 300))
    restart_cmd = os.getenv("NAPCAT_WATCHDOG_RESTART_CMD") or "./scripts/restart-napcat.sh"
    last_restart_at = 0.0
    last_state = "unknown"

    print(f"NapCat watchdog started, interval={interval}s", flush=True)
    while True:
        ok, detail = check_napcat()
        now = time.time()
        state = "online" if ok else "offline"
        if state != last_state:
            print(f"NapCat state changed: {state}: {detail}", flush=True)
            last_state = state

        if not ok and now - last_restart_at >= cooldown:
            last_restart_at = now
            subject = "[qq-cf-bot] NapCat offline, restarting"
            body = f"NapCat health check failed on {socket.gethostname()}.\n\n{detail}\n\nRestart command:\n{restart_cmd}\n"
            print(body, flush=True)
            notify(subject, body)
            restart(restart_cmd)

        time.sleep(interval)


def check_napcat() -> Tuple[bool, str]:
    base_url = (os.getenv("NAPCAT_WATCHDOG_ONEBOT_URL") or os.getenv("ONEBOT_HTTP_URL") or "http://127.0.0.1:3000").rstrip("/")
    token = os.getenv("ONEBOT_ACCESS_TOKEN", "")

    try:
        payload = _post_json(base_url + "/get_status", {}, token)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        online = data.get("online")
        good = data.get("good")
        if online is False or good is False:
            return False, f"get_status returned offline: {payload}"
        if online is True or good is True:
            return True, f"get_status OK: {payload}"
    except Exception as exc:
        status_error = exc
    else:
        status_error = RuntimeError(f"get_status did not expose online/good fields: {payload}")

    try:
        payload = _post_json(base_url + "/get_login_info", {}, token)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        if payload.get("status") == "ok" and (data.get("user_id") or payload.get("user_id")):
            return True, f"get_login_info OK: {payload}"
        return False, f"get_login_info returned unexpected payload after status issue {status_error}: {payload}"
    except Exception as exc:
        return False, f"get_status failed: {status_error}; get_login_info failed: {exc}"


def restart(command: str) -> None:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=ROOT_DIR,
            text=True,
            capture_output=True,
            timeout=180,
        )
    except Exception as exc:
        notify("[qq-cf-bot] NapCat restart command failed", f"Command: {command}\n\n{exc}")
        return

    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if result.returncode == 0:
        notify("[qq-cf-bot] NapCat restart command finished", output[-4000:])
    else:
        notify("[qq-cf-bot] NapCat restart command failed", f"Exit code: {result.returncode}\n\n{output[-4000:]}")


def notify(subject: str, body: str) -> None:
    recipient = os.getenv("NAPCAT_WATCHDOG_NOTIFY_EMAIL", "").strip()
    if not recipient:
        return
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_user = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    if not smtp_host or not smtp_user or not smtp_password:
        print("Email notification skipped: SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD is not fully configured.", flush=True)
        return

    sender = os.getenv("SMTP_FROM", "").strip() or smtp_user
    port = _int_env("SMTP_PORT", 465)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if _bool_env("SMTP_SSL", True):
        with smtplib.SMTP_SSL(smtp_host, port, timeout=20) as client:
            client.login(smtp_user, smtp_password)
            client.send_message(message)
    else:
        with smtplib.SMTP(smtp_host, port, timeout=20) as client:
            if _bool_env("SMTP_STARTTLS", True):
                client.starttls()
            client.login(smtp_user, smtp_password)
            client.send_message(message)


def _post_json(url: str, payload: dict, token: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "qq-cf-bot-watchdog/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    return json.loads(body or "{}")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


if __name__ == "__main__":
    main()
