#!/usr/bin/env python3
"""The one morning report. One message a day, from the orchestrator, built from what each intern left overnight.

Each intern's scheduled morning run writes a short contribution to team/inbox/<date>/<agent>.md: the human's
actions for the day, with a time and where to look ("10:00 call Acme, prep on the sheet"), never a report on
what the agent did. The orchestrator's run reads them, writes the brief as JSON, and this script renders it:

  Direction (one line) · Start here (3 timed items) · Your day · one short section per intern (sales 3 lines,
  marketing 2, finance only if money needs you) · one decision · orders to the team · "add to your to-do?"

Kept under about 250 words on purpose: a brief you read beats a report you skim.

Usage:  brief.py inputs                 print today's contributions (for the orchestrator's run)
        brief.py render FILE.json       render the brief as plain text (stdout); --slack for Slack mrkdwn
        brief.py --test"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

LIMITS = {"sales": 3, "marketing": 2, "finance": 2}


def inputs(date=None):
    date = date or common.today()
    folder = os.path.join(common.INBOX, date)
    out = [f"Contributions for {date}:"]
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    if not any(n.endswith(".md") for n in names):
        out.append("(none yet)")
    for name in names:
        if name.endswith(".md") and not name.startswith("orders-") and name not in ("cards.md", "report.md"):
            out += ["", f"## {name[:-3]}", common.read(os.path.join(folder, name), 5000).strip()]
    stuck = waiting_cards()
    if stuck:
        out += ["", "## Signed off but not sent (tell the human: send these yourself, or ask why)"] + stuck
    return "\n".join(out)


def waiting_cards():
    """Cards you signed off that haven't gone: past the undo with no send run (a tool without the guard hook) or failed."""
    import approvals
    ready = set(approvals.ready())
    return [f"- {c['subject']} to {c['to']} ({c['agent']}, card {cid}" + (f", failed: {c.get('note')}" if c["state"] == "failed" else "") + ")"
            for cid, c in approvals._load().items() if cid in ready or c["state"] == "failed"]


def render(data, slack=False):
    """data: {date, direction, start_here: [..], day: [..], sections: {sales: [..], marketing: [..], finance: [..]},
    decision, todo: [{title, why, due}]}. Orders are read from orders.py, never retyped."""
    import orders
    b = ("*{}*" if slack else "{}").format
    date = data.get("date") or common.today()
    d = datetime.date.fromisoformat(date)
    lines = [b(f"{d:%a %d %b}: {data.get('direction', '').strip()}"), ""]
    if data.get("start_here"):
        lines += [b("Start here")] + [f"{i}. {x}" for i, x in enumerate(data["start_here"][:3], 1)] + [""]
    if data.get("day"):
        lines += [b("Your day")] + [f"• {x}" for x in data["day"]] + [""]
    for key, limit in LIMITS.items():
        items = (data.get("sections") or {}).get(key) or []
        if items:
            lines += [b(key.capitalize())] + [f"• {x}" for x in items[:limit]] + [""]
    if data.get("decision"):
        lines += [b("One decision: ") + data["decision"], ""]
    given, recap, prev = orders.for_brief(date)
    if given or recap:
        lines += [b("Orders to the team")] + [f"• {x}" for x in given]
        if recap:
            lines.append(("_{}_" if slack else "{}").format(f"Last orders, {prev}: {recap}"))
        lines.append("")
    if data.get("todo"):
        lines += [b("Add to your to-do?")] + [f"{i}. {t.get('title')} · {t.get('why', '')} · due {t.get('due', '?')}"
                                                for i, t in enumerate(data["todo"], 1)]
        lines.append("Reply with the numbers to add.")
    return "\n".join(lines).strip() + "\n"


def test():
    import tempfile
    common.INBOX = tempfile.mkdtemp()
    data = {"date": "2026-01-05", "direction": "Book two meetings.", "start_here": ["09:00 Call Acme"],
            "day": ["10:00 Call with Northwind"], "sections": {"sales": ["Acme replied: draft on the sheet"]},
            "decision": "Load the new list?", "todo": [{"title": "Fix the site", "why": "typo", "due": "Fri"}]}
    out = render(data)
    ok = out.startswith("Mon 05 Jan: Book two meetings.") and "Start here" in out and "One decision" in out
    ok = ok and "Fix the site" in out and "Orders to the team" not in out
    ok = ok and "(none yet)" in inputs("2026-01-05")
    print("brief: ok" if ok else "brief: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    elif sys.argv[1:2] == ["inputs"]:
        print(inputs(sys.argv[2] if len(sys.argv) > 2 else None))
    elif sys.argv[1:2] == ["render"] and len(sys.argv) > 2:
        with open(sys.argv[2]) as f:
            print(render(json.load(f), slack="--slack" in sys.argv))
    else:
        print(__doc__)
