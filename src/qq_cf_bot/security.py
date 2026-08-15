from __future__ import annotations

import re


_SECRET_TOKEN_RE = re.compile(
    r"\b(?:sk|tskey|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9._/+={}\[\]-]{10,}\b",
    re.IGNORECASE,
)
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9._/+={}\[\]-]{10,}\b", re.IGNORECASE)
_ENV_ASSIGN_RE = re.compile(
    r"\b(?:OPENAI_API_KEY|JUDGE_API_KEY|TRANSLATE_API_KEY|ONEBOT_ACCESS_TOKEN|CF_PASSWORD|"
    r"TAILSCALE_AUTHKEY|AUTHORIZATION|PASSWORD|TOKEN|API_KEY)\s*=\s*[^\s,;]+",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.IGNORECASE)
_PROBLEM_ID_RE = re.compile(r"\b(?:CF)?\d{1,6}[A-Z][0-9]?\b")

_LEAK_MARKER_RE = re.compile(
    r"(system\s*prompt|developer\s*message|api[_ -]?key|authorization|bearer|password|token|"
    r"\.env|环境变量|系统提示|提示词|密钥|密码|令牌|授权头|参考材料|题解链接|题目链接|"
    r"codeforces|luogu|洛谷)",
    re.IGNORECASE,
)
_EXFILTRATION_REQUEST_RE = re.compile(
    r"(忽略.{0,20}(上面|之前|系统|规则|指令)|"
    r"(输出|告诉|显示|泄露|打印|给出).{0,40}"
    r"(系统|提示词|prompt|token|密钥|密码|api|环境变量|\.env|authorization|bearer|参考材料|链接|题号)|"
    r"ignore.{0,20}(previous|above|system|instruction)|"
    r"(print|show|reveal|tell).{0,40}(system|prompt|token|password|api|secret|env|authorization|bearer))",
    re.IGNORECASE,
)


def redact_sensitive_text(text: str) -> str:
    redacted = _BEARER_RE.sub("Bearer [已隐藏]", text)
    redacted = _SECRET_TOKEN_RE.sub("[密钥已隐藏]", redacted)
    redacted = _ENV_ASSIGN_RE.sub(lambda match: match.group(0).split("=", 1)[0] + "=[已隐藏]", redacted)
    return redacted


def looks_like_secret_exfiltration_request(text: str) -> bool:
    return bool(_EXFILTRATION_REQUEST_RE.search(text))


def safe_judge_reason(reason: str, accepted: bool) -> str:
    if accepted:
        return "通过"

    text = redact_sensitive_text(reason.strip())
    if not text:
        return "做法不完整。"
    if _LEAK_MARKER_RE.search(text):
        return "做法不完整或包含与解题无关的指令，无法通过。"

    text = _URL_RE.sub("[链接已隐藏]", text)
    text = _PROBLEM_ID_RE.sub("[题号已隐藏]", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 240:
        text = text[:240].rstrip() + "..."
    return text or "做法不完整。"
