#!/usr/bin/env python3
"""Which hook style earns replies and saves: the numbers behind Chris's Friday /score.

Every post the human publishes goes in out/posts.csv with its hook tag (question, story, number, joke) and, once the
numbers settle, its replies and saves. The score ranks the hook styles over a window, weighting a reply above a save
(a reply is a conversation, a save is a bookmark). A style needs at least MIN_POSTS posts before it can win or lose,
so one lucky post never rewrites the playbook.

Usage:  hooks.py log --date 2026-03-02 --hook story [--replies 4] [--saves 9] [--note "..."]   (adds or updates a post)
        hooks.py score [--days 28] [--json]       the ranking, the winner and loser, and lines for PLAYBOOK.md
        hooks.py --test"""
import argparse
import csv
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
POSTS = os.environ.get("CHRIS_POSTS") or os.path.join(HERE, "..", "out", "posts.csv")
FIELDS = ["date", "hook", "replies", "saves", "note"]
HOOKS = ("question", "story", "number", "joke")
REPLY_WEIGHT, SAVE_WEIGHT = 3, 1
MIN_POSTS = 2


def load(path=None):
    try:
        with open(path or POSTS, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def save(rows, path=None):
    path = path or POSTS
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def log(date, hook, replies=None, saves=None, note="", path=None):
    """One post a day: logging the same date again updates it (numbers arrive a day or two later)."""
    hook = hook.strip().lower().replace("hook:", "")
    if hook not in HOOKS:
        raise ValueError(f"hook must be one of {', '.join(HOOKS)}")
    datetime.date.fromisoformat(date)
    rows = [r for r in load(path) if r["date"] != date]
    old = next((r for r in load(path) if r["date"] == date), {})
    rows.append({"date": date, "hook": hook,
                 "replies": replies if replies is not None else old.get("replies", ""),
                 "saves": saves if saves is not None else old.get("saves", ""),
                 "note": note or old.get("note", "")})
    save(sorted(rows, key=lambda r: r["date"]), path)


def score(days=28, today=None, path=None):
    today = today or datetime.date.today()
    start = today - datetime.timedelta(days=days)
    by = {}
    for r in load(path):
        if r["replies"] == "" or r["saves"] == "" or datetime.date.fromisoformat(r["date"]) <= start:
            continue  # numbers not in yet, or outside the window
        b = by.setdefault(r["hook"], {"posts": 0, "replies": 0, "saves": 0})
        b["posts"] += 1
        b["replies"] += int(r["replies"])
        b["saves"] += int(r["saves"])
    ranking = []
    for hook, b in by.items():
        per_post = (REPLY_WEIGHT * b["replies"] + SAVE_WEIGHT * b["saves"]) / b["posts"]
        ranking.append(dict(b, hook=hook, per_post=round(per_post, 1)))
    ranking.sort(key=lambda x: -x["per_post"])
    eligible = [x for x in ranking if x["posts"] >= MIN_POSTS]
    winner = eligible[0]["hook"] if len(eligible) >= 2 else None
    loser = eligible[-1]["hook"] if len(eligible) >= 2 else None
    untested = [h for h in HOOKS if h not in by]
    return {"from": (start + datetime.timedelta(days=1)).isoformat(), "to": today.isoformat(), "ranking": ranking,
            "winner": winner, "loser": loser, "untested": untested}


def render(s):
    if not s["ranking"]:
        return f"No scored posts between {s['from']} and {s['to']}: log the numbers with `hooks.py log`."
    lines = [f"Hooks, {s['from']} to {s['to']} (a reply counts {REPLY_WEIGHT}, a save {SAVE_WEIGHT}, per post):"]
    for x in s["ranking"]:
        lines.append(f"- {x['hook']}: {x['per_post']} a post ({x['posts']} posts, {x['replies']} replies, {x['saves']} saves)")
    if s["winner"]:
        w = next(x for x in s["ranking"] if x["hook"] == s["winner"])
        lines.append(f"PLAYBOOK.md: default to `hook:{s['winner']}` ({w['per_post']} a post over {w['posts']} posts, "
                     f"{s['from']} to {s['to']}); retire `hook:{s['loser']}` as a default.")
    else:
        lines.append(f"Too early to call: a style needs {MIN_POSTS} scored posts and there must be two such styles.")
    if s["untested"]:
        lines.append("Untested: " + ", ".join(s["untested"]) + ". Try one next week.")
    return "\n".join(lines)


def test():
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), "posts.csv")
    today = datetime.date(2026, 3, 13)
    for d, h, r, s in [("2026-03-02", "story", 6, 10), ("2026-03-03", "number", 1, 4), ("2026-03-04", "story", 4, 8),
                       ("2026-03-05", "number", 2, 2), ("2026-03-06", "question", 9, 1), ("2026-01-05", "joke", 50, 50)]:
        log(d, h, r, s, path=path)
    log("2026-03-09", "hook:story", path=path)                     # numbers not in yet: left out of the score
    log("2026-03-09", "story", replies=3, path=path)               # still no saves: still left out
    s = score(28, today, path)
    ok = [x["hook"] for x in s["ranking"]] == ["question", "story", "number"]
    ok &= s["winner"] == "story" and s["loser"] == "number"       # question has one post: can't win yet
    ok &= "joke" in s["untested"]                                   # outside the window
    ok &= "default to `hook:story`" in render(s)
    ok &= len(load(path)) == 7 and next(r for r in load(path) if r["date"] == "2026-03-09")["replies"] == "3"
    try:
        log("2026-03-10", "rant", path=path)
        ok = False
    except ValueError:
        pass
    ok &= render(score(28, today, path=os.path.join(tempfile.mkdtemp(), "none.csv"))).startswith("No scored posts")
    log("2026-03-10", "joke", 1, 1, path=path)
    ok &= "Too early" not in render(score(28, today, path))
    print("hooks: ok" if ok else f"hooks: FAIL {s}")
    return 0 if ok else 1


def main():
    if "--test" in sys.argv:
        return test()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("--date", required=True)
    lg.add_argument("--hook", required=True)
    lg.add_argument("--replies", type=int)
    lg.add_argument("--saves", type=int)
    lg.add_argument("--note", default="")
    sc = sub.add_parser("score")
    sc.add_argument("--days", type=int, default=28)
    sc.add_argument("--json", action="store_true")
    a = p.parse_args()
    if a.cmd == "log":
        log(a.date, a.hook, a.replies, a.saves, a.note)
        print(f"logged {a.date} hook:{a.hook.replace('hook:', '')}")
    else:
        s = score(a.days)
        print(json.dumps(s, indent=1) if a.json else render(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
