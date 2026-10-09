#!/usr/bin/env python3
"""Orders: how the orchestrator gives the other interns work, and how they report back.

One plan, not four. The orchestrator writes today's orders once (team/inbox/<date>/orders.json); each intern reads
only its own, does what fits its rules, and reports done, blocked or skipped with a line of why
(team/inbox/<date>/orders-<agent>.md). The morning report shows the orders and what the last ones came to, so
the human sees the plan without chasing anyone.

Rules checked in code, because team rules beat orders: an order can never ask an intern to send, post, delete,
spend money or write to the calendar. Those stay with the human (or the orchestrator, after the human's OK).

Usage:  orders.py give --json FILE      [{"to": "ella", "do": "…", "why": "…"}, …]  (orchestrator only)
        orders.py show --as AGENT       the latest orders for AGENT, with its reports
        orders.py report --as AGENT --id N --status done|blocked|skipped [--note "…"]
        orders.py summary [--date D]    today's orders and the last ones not done
        orders.py --test"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

LOOKBACK_DAYS = 4
MAX_DO = 100
FORBIDDEN = re.compile(r"\b(send|sends|sending|publish\w*|delete|deletes|archive|pay|transfer|invite)\b|\bpost(s|ing)? (it |this |that )?(on|to)\b", re.I)
MARK = {"open": "·", "done": "✓", "blocked": "⚠", "skipped": "–"}


def orders_file(date):
    return os.path.join(common.INBOX, date, "orders.json")


def report_file(date, agent):
    return os.path.join(common.INBOX, date, f"orders-{agent}.md")


def load(date):
    try:
        with open(orders_file(date)) as f:
            return json.load(f).get("orders", [])
    except (OSError, ValueError):
        return []


def validate(order, agents):
    errs = []
    to = str(order.get("to") or "").strip()
    do = str(order.get("do") or "").strip()
    why = str(order.get("why") or "").strip()
    if agents and to not in agents:
        errs.append(f"unknown agent '{to}'")
    if not do:
        errs.append("every order needs a 'do'")
    if len(do) > MAX_DO:
        errs.append(f"'do' is over {MAX_DO} characters: one clear job, the context goes in 'why'")
    if not why:
        errs.append("every order needs a 'why'")
    if FORBIDDEN.search(do):
        errs.append("interns never send, post, delete, pay or invite on an order: that is the human's call")
    return errs


def reports(date, agent):
    out = {}
    for line in common.read(report_file(date, agent)).splitlines():
        m = re.match(r"- #(\d+) \S+ (done|blocked|skipped) \S+: ?(.*)", line)
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(3))
    return out


def with_status(date, orders):
    seen = {}
    for o in orders:
        if o["to"] not in seen:
            seen[o["to"]] = reports(date, o["to"])
        status, note = seen[o["to"]].get(o["id"], ("open", ""))
        yield dict(o, status=status, note=note)


def latest_date(agent=None, before=None):
    start = datetime.date.fromisoformat(before) - datetime.timedelta(days=1) if before else common.now().date()
    for i in range(LOOKBACK_DAYS + 1):
        d = (start - datetime.timedelta(days=i)).isoformat()
        mine = [o for o in load(d) if agent is None or o["to"] == agent]
        if mine:
            return d
    return None


def give(path, date=None, agents=None):
    with open(path) as f:
        new = json.load(f)
    agents = agents if agents is not None else common.agent_names()
    errs = [f"order {i + 1}: {e}" for i, o in enumerate(new) for e in validate(o, agents)]
    if errs:
        return {"blocked": errs}
    date = date or common.today()
    have = load(date)
    nid = max([o["id"] for o in have], default=0)
    for o in new:
        nid += 1
        have.append({"id": nid, "to": o["to"].strip(), "do": o["do"].strip(), "why": o["why"].strip(),
                     "at": f"{common.now():%H:%M}"})
    os.makedirs(os.path.dirname(orders_file(date)), exist_ok=True)
    tmp = orders_file(date) + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"date": date, "orders": have}, f, indent=2, ensure_ascii=False)
    os.replace(tmp, orders_file(date))
    return {"given": len(new), "date": date}


def show(agent):
    date = latest_date(agent)
    if not date:
        return f"No orders for {agent}."
    lines = [f"Orders from the orchestrator, {date} (they lapse unless re-issued). Do the open ones that fit this "
             f"run, inside your rules. Report each: orders.py report --as {agent} --id N --status done|blocked|skipped "
             f"--note \"why\""]
    for o in with_status(date, load(date)):
        if o["to"] == agent:
            lines.append(f"#{o['id']} [{o['status']}] {o['do']} (why: {o['why']})" + (f" · {o['note']}" if o["note"] else ""))
    return "\n".join(lines)


def report(agent, oid, status, note="", date=None):
    date = date or latest_date(agent)
    mine = {o["id"]: o for o in load(date or "") if o["to"] == agent}
    if oid not in mine:
        return f"No order #{oid} for {agent} on {date}."
    if status != "done" and not note.strip():
        return "Say why: --note is required for blocked or skipped."
    os.makedirs(os.path.dirname(report_file(date, agent)), exist_ok=True)
    clean = re.sub(r"\s+", " ", note.strip())[:200]  # outside the f-string: Python 3.9-3.11 forbid backslashes inside one
    with open(report_file(date, agent), "a") as f:
        f.write(f"- #{oid} {MARK[status]} {status} {common.now():%H:%M}: {clean}\n")
    return f"reported #{oid} {status}"


def for_brief(date):
    """Today's orders as 'name · job' lines, and one quiet recap of the last orders."""
    todays = load(date)
    today = [f"{o['to']} · {o['do']}" for o in todays]
    prev = latest_date(before=date)
    recap = ""
    if prev:
        olds = list(with_status(prev, load(prev)))
        counts = {s: sum(1 for o in olds if o["status"] == s) for s in ("done", "skipped", "blocked")}
        parts = [f"{n} {s}" for s, n in counts.items() if n]
        still = [f"{o['to']} · {o['do']}" for o in olds if o["status"] == "open"]
        recap = " · ".join(parts) + (" · still open: " + "; ".join(still) if still else "")
    return today, recap, prev


def test():
    import tempfile
    common.INBOX = tempfile.mkdtemp()
    tmp = os.path.join(common.INBOX, "o.json")
    with open(tmp, "w") as f:
        json.dump([{"to": "ella", "do": "Shortlist 20 warm contacts for Monday", "why": "the sheet is thin"}], f)
    r = give(tmp, "2026-01-05", agents=["theo", "ella"])
    ok = r.get("given") == 1
    with open(tmp, "w") as f:
        json.dump([{"to": "ella", "do": "Send the proposal to the client", "why": "x"}], f)
    ok = ok and "blocked" in give(tmp, "2026-01-05", agents=["theo", "ella"])
    ok = ok and "Shortlist" in show("ella") if latest_date("ella") else ok
    common.now = lambda: datetime.datetime(2026, 1, 5, 9, 0)
    ok = ok and report("ella", 1, "done", "", "2026-01-05").startswith("reported")
    today, recap, prev = for_brief("2026-01-06")
    ok = ok and recap.startswith("1 done") and prev == "2026-01-05"
    print("orders: ok" if ok else "orders: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("give"); g.add_argument("--json", required=True); g.add_argument("--date")
    s = sub.add_parser("show"); s.add_argument("--as", dest="agent", required=True)
    r = sub.add_parser("report"); r.add_argument("--as", dest="agent", required=True); r.add_argument("--id", type=int, required=True)
    r.add_argument("--status", choices=["done", "blocked", "skipped"], required=True); r.add_argument("--note", default=""); r.add_argument("--date")
    m = sub.add_parser("summary"); m.add_argument("--date")
    a = p.parse_args()
    if a.cmd == "give":
        print(json.dumps(give(a.json, a.date)))
    elif a.cmd == "show":
        print(show(a.agent))
    elif a.cmd == "report":
        print(report(a.agent, a.id, a.status, a.note, a.date))
    else:
        today, recap, prev = for_brief(a.date or common.today())
        print("Today:", *today, sep="\n  ") if today else print("Today: none yet")
        if prev:
            print(f"Last orders ({prev}): {recap}")
