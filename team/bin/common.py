#!/usr/bin/env python3
"""Shared helpers for the team scripts: where things are, the team config, local time in the team's timezone.

Every script in this folder imports from here, so there is one place to change a path. Python 3.9+, stdlib only."""
import datetime
import json
import os
import re

BIN = os.path.dirname(os.path.abspath(__file__))
TEAM = os.path.dirname(BIN)
ROOT = os.path.dirname(TEAM)
AGENTS = os.path.join(ROOT, "agents")
INBOX = os.path.join(TEAM, "inbox")
STATUS = os.path.join(TEAM, "status")
LOGS = os.path.join(TEAM, "logs")
CONFIG = os.path.join(TEAM, "team.json")  # written by install.py, gitignored


def load_config():
    """team.json: {"timezone": "...", "owner": {...}, "agents": {"theo": {"role": "orchestrator", ...}}}."""
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"timezone": "UTC", "agents": {}}


def now():
    """Local time in the team's timezone (team.json), or UTC if that is missing."""
    tz = load_config().get("timezone") or "UTC"
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(tz))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def today():
    return now().date().isoformat()


def agent_dir(name):
    return os.path.join(AGENTS, name)


def orchestrator():
    """The one agent allowed to send (the head intern, who orchestrates the rest). Default 'theo' until install.py renames."""
    for name, a in load_config().get("agents", {}).items():
        if a.get("role") == "orchestrator":
            return name
    return "theo"


def agent_names():
    cfg = load_config().get("agents", {})
    if cfg:
        return list(cfg)
    try:
        return sorted(d for d in os.listdir(AGENTS) if os.path.isdir(os.path.join(AGENTS, d)) and not d.startswith("."))
    except OSError:
        return []


def read(path, limit=60000):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    return text if len(text) <= limit else text[:limit] + "\n… (cut)"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def log_line(path, line):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{now():%Y-%m-%d %H:%M} {line}\n")
