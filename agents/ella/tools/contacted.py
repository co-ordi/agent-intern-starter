#!/usr/bin/env python3
"""Ella's already-contacted check: nobody gets a cold message while they're in a live conversation, and nobody gets
the same cold approach twice in a row.

Every touch goes in a small log (date, name, email, channel, what happened). Before Ella puts anyone on the day's
sheet as a new contact, she runs the check:

    python3 contacted.py check --email jo@example.com          # or --name "Jo Bloggs"
    python3 contacted.py log --email jo@example.com --name "Jo Bloggs" --channel email --outcome sent
    python3 contacted.py log --email jo@example.com --channel email --outcome replied

Verdicts:
    LIVE   they replied or you met in the last 14 days: a follow-up, never a cold item
    HOLD   a cold touch in the last 90 days with no reply: not again yet, and never the same channel twice
    WARM   they replied at some point before: a warm message, never a cold one
    OK     nothing on record, or long enough ago
    NO     they said no or asked not to be contacted: never again

The log lives in Ella's out/ folder (agents/<sales intern>/out/contacted.csv), which never goes in git. Seed it from
your CRM or email export once; Ella adds a line for every touch after that. Python 3.9+, standard library only.

    contacted.py --test      self-test"""
import argparse
import csv
import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(HERE), "out", "contacted.csv")
FIELDS = ["date", "name", "email", "channel", "outcome"]
LIVE_DAYS, HOLD_DAYS = 14, 90
REPLY = {"replied", "met", "meeting", "call"}
NEVER = {"no", "opted_out", "unsubscribe", "not_interested"}


def load(path=LOG):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _match(row, email, name):
    if email and row.get("email", "").strip().lower() == email.strip().lower():
        return True
    return bool(name) and not email and row.get("name", "").strip().lower() == name.strip().lower()


def verdict(rows, email=None, name=None, today=None):
    """(verdict, reason) for one person."""
    today = today or datetime.date.today()
    mine = sorted((r for r in rows if _match(r, email, name)), key=lambda r: r["date"])
    if not mine:
        return "OK", "nothing on record"
    for r in mine:
        if r.get("outcome", "").lower() in NEVER:
            return "NO", f"{r['outcome']} on {r['date']}: never again"
    age = lambda r: (today - datetime.date.fromisoformat(r["date"])).days  # noqa: E731
    replies = [r for r in mine if r.get("outcome", "").lower() in REPLY]
    if replies and age(replies[-1]) <= LIVE_DAYS:
        return "LIVE", f"{replies[-1]['outcome']} {age(replies[-1])} days ago: follow up, don't cold-contact"
    last = mine[-1]
    if not replies and age(last) <= HOLD_DAYS:
        used = sorted({r.get("channel", "") for r in mine})
        return "HOLD", f"cold touch {age(last)} days ago, no reply; channels used: {', '.join(used)}"
    if replies:
        return "WARM", f"replied on {replies[-1]['date']}: a warm message, not a cold one"
    return "OK", f"last touch {age(last)} days ago, no reply"


def log(path, **row):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k) or "" for k in FIELDS})


def main(argv=None):
    p = argparse.ArgumentParser(description="Ella's already-contacted check.")
    p.add_argument("cmd", nargs="?", choices=["check", "log"])
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--channel", default="")
    p.add_argument("--outcome", default="sent")
    p.add_argument("--date", default=str(datetime.date.today()))
    p.add_argument("--file", default=LOG)
    p.add_argument("--test", action="store_true")
    a = p.parse_args(argv)
    if a.test:
        return selftest()
    if not a.cmd or not (a.email or a.name):
        p.error("check or log, with --email or --name")
    if a.cmd == "log":
        log(a.file, date=a.date, name=a.name, email=a.email, channel=a.channel, outcome=a.outcome)
        print("logged")
        return 0
    v, why = verdict(load(a.file), a.email, a.name)
    print(f"{v}  {why}")
    return 0


def selftest():
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "c.csv")
    t = datetime.date(2026, 10, 9)
    d = lambda n: str(t - datetime.timedelta(days=n))  # noqa: E731
    log(path, date=d(5), name="Jo Example", email="jo@example.com", channel="email", outcome="replied")
    log(path, date=d(30), name="Sam Example", email="sam@example.com", channel="linkedin", outcome="sent")
    log(path, date=d(200), name="Ali Example", email="ali@example.com", channel="email", outcome="replied")
    log(path, date=d(10), name="Kim Example", email="kim@example.com", channel="email", outcome="opted_out")
    log(path, date=d(120), name="Lee Example", email="lee@example.com", channel="email", outcome="sent")
    rows = load(path)
    got = [verdict(rows, e, today=t)[0] for e in
           ("jo@example.com", "sam@example.com", "ali@example.com", "kim@example.com", "lee@example.com", "new@example.com")]
    ok = got == ["LIVE", "HOLD", "WARM", "NO", "OK", "OK"]
    ok &= verdict(rows, name="Sam Example", today=t)[0] == "HOLD" and "linkedin" in verdict(rows, "sam@example.com", today=t)[1]
    print("contacted: ok" if ok else f"contacted: FAIL {got}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
