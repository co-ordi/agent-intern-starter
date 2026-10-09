#!/usr/bin/env python3
"""The voice check. Anything an intern writes in your name (emails, posts, replies) is checked against the hard
lines of your voice before it reaches you: no em dashes, none of the phrases you've banned, no stock
AI framing. The intern fixes what this flags; your own edits are never checked.

The banned list is yours to grow: team/voice/VOICE.md holds the full voice guide (how you write, examples
you like) and a fenced ```banned block of phrases, one per line. This script reads that block.

Usage:  voice.py check FILE | -      {"ok": true|false, "issues": [...]}, exit 1 on issues
        voice.py --test"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

VOICE = os.path.join(common.TEAM, "voice", "VOICE.md")
DEFAULT_BANNED = [
    "I hope this email finds you well", "I'd be happy to", "Great question", "Certainly!", "delve", "leverage",
    "game-changer", "in today's fast-paced", "I wanted to reach out", "touch base", "circle back", "synergy",
    "it's not just", "isn't just", "the exact", "that's exactly",
]


def banned_phrases(path=VOICE):
    text = common.read(path)
    m = re.search(r"```banned\n(.*?)```", text, re.S)
    if not m:
        return DEFAULT_BANNED
    return [l.strip() for l in m.group(1).splitlines() if l.strip() and not l.startswith("#")]


def check(text, phrases=None):
    issues = []
    if "—" in text or "–" in text:
        issues.append("em or en dash: use a comma, a colon or a full stop")
    low = text.lower()
    for p in phrases if phrases is not None else banned_phrases():
        if p.lower() in low:
            issues.append(f"banned phrase: {p}")
    if re.search(r"\b(\w+), not (\w+)\b", text) and re.search(r"\bnot (just|only)\b", low):
        issues.append("contrast trope ('X, not Y' / 'not just X'): say what it is")
    return {"ok": not issues, "issues": issues}


def test():
    ok = check("Hi Sam, Tuesday at 2 works. Jo", [])["ok"]
    ok = ok and not check("Great question — let's delve in", DEFAULT_BANNED)["ok"]
    ok = ok and len(check("I'd be happy to help", DEFAULT_BANNED)["issues"]) == 1
    print("voice: ok" if ok else "voice: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    elif sys.argv[1:2] == ["check"] and len(sys.argv) > 2:
        src = sys.stdin.read() if sys.argv[2] == "-" else common.read(sys.argv[2])
        r = check(src)
        print(json.dumps(r))
        sys.exit(0 if r["ok"] else 1)
    else:
        print(__doc__)
