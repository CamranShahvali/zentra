"""Zentra audit trail — every tool the agent uses gets logged, append-only.

This log is a FEATURE: it is the 'Know Your Agent' evidence a bank would demand.
"""
from __future__ import annotations

import json
import time

from . import config


def log(tool: str, args_summary: str, result_summary: str) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tool": tool,
        "args": args_summary[:300],
        "result": result_summary[:300],
    }
    with config.AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read(limit: int = 200) -> list[dict]:
    if not config.AUDIT_LOG.exists():
        return []
    lines = config.AUDIT_LOG.read_text().strip().splitlines()
    return [json.loads(l) for l in lines[-limit:]]


def clear() -> None:
    if config.AUDIT_LOG.exists():
        config.AUDIT_LOG.unlink()
