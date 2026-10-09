#!/usr/bin/env python3
"""Start-up context for an intern. Runs as a SessionStart hook: `boot.py <agent>`.

The problem it solves: a fresh Claude session knows nothing about yesterday. This prints, into the session's
context, everything the intern needs so it never starts from zero:

  1. who it is (AGENT.md is the system prompt; this adds the live state),
  2. its memory (memory/MEMORY.md), its open questions for you, and the tail of its run log,
  3. today's shared team notes (team/inbox/<today>/), so handoffs from the other interns are visible,
  4. orders from the orchestrator (orders.py show), and its playbook defaults,
  5. the time the session started, labelled as such.

That last point matters: a session opened at midnight is still open at 9am, so the stamp says
"Session started", and the intern checks the clock before saying anything time-sensitive.

Usage:  boot.py <agent>          print the context (the hook's stdout goes into the session)
        boot.py <agent> --dry    same, but say what would be read without reading memory
        boot.py --test           self-test"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SECTIONS = [
    ("YOUR MEMORY (memory/MEMORY.md: update it in place when something durable happens)", "memory/MEMORY.md"),
    ("OPEN QUESTIONS FOR YOUR HUMAN (memory/questions.md)", "memory/questions.md"),
    ("YOUR PLAYBOOK (PLAYBOOK.md: defaults with evidence)", "PLAYBOOK.md"),
    ("HOW YOU OPERATE (OPERATING.md)", "OPERATING.md"),
]


def team_notes(day):
    folder = os.path.join(common.INBOX, day)
    if not os.path.isdir(folder):
        return ""
    parts = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".md"):
            parts.append(f"--- {name} ---\n" + common.read(os.path.join(folder, name), 4000))
    return "\n\n".join(parts)


def orders_for(agent):
    try:
        out = subprocess.run([sys.executable, os.path.join(common.BIN, "orders.py"), "show", "--as", agent],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return ""


def build(agent, dry=False):
    home = common.agent_dir(agent)
    if not os.path.isdir(home):
        return f"boot.py: no agent folder at {home}. Run install.py first."
    when = common.now()
    cfg = common.load_config().get("agents", {}).get(agent, {})
    role = cfg.get("title") or agent
    lines = [
        f"=== START-UP CONTEXT: you are {role}. Stay in character for the whole session. Use what follows before "
        f"answering; never start from zero. ===",
        f"Session started: {when:%a %d %b %Y %H:%M} ({common.load_config().get('timezone', 'UTC')}). This goes stale: "
        f"when a task depends on the time or date, run `date` first; if the day has changed, re-read "
        f"team/inbox/<today>/ before trusting the notes below.",
    ]
    if os.environ.get("TEAM_RUN") == "1":
        lines.append(f"SCHEDULED RUN ({os.environ.get('TEAM_JOB', 'job')}): nobody is watching and your reply only reaches "
                     f"a log. Never ask questions; put anything your human must decide in your contribution as "
                     f"`Decision:`. Anything they must see goes in a file in team/inbox/<today>/ (and Slack if wired). Run "
                     f"each script as its own command from your folder (`python3 ../../team/bin/<script>.py ...`, "
                     f"`python3 tools/<script>.py ...`): cd, chained commands and python3 -c need a permission nobody "
                     f"is here to give.")
    if dry:
        lines.append("(dry run: memory and notes not read)")
        return "\n".join(lines)
    for title, rel in SECTIONS:
        text = common.read(os.path.join(home, rel))
        if text.strip():
            lines += ["", f"--- {title} ---", text.strip()]
    notes = team_notes(when.date().isoformat())
    lines += ["", f"--- TEAM NOTES AS AT SESSION START (team/inbox/{when.date().isoformat()}/) ---",
              notes.strip() or "(nothing yet today)"]
    orders = orders_for(agent)
    if orders:
        lines += ["", "--- ORDERS FROM THE ORCHESTRATOR (team/bin/orders.py) ---", orders]
    log = common.read(os.path.join(home, "memory", "log.md"))
    tail = "\n".join(log.strip().splitlines()[-8:])
    if tail:
        lines += ["", "--- YOUR LAST RUNS (memory/log.md, newest last) ---", tail]
    return "\n".join(lines)


def test():
    import tempfile
    tmp = tempfile.mkdtemp()
    common.AGENTS = tmp
    os.makedirs(os.path.join(tmp, "zed", "memory"))
    with open(os.path.join(tmp, "zed", "memory", "MEMORY.md"), "w") as f:
        f.write("# Zed memory\n## Now\n- first day\n")
    out = build("zed")
    ok = "Session started:" in out and "first day" in out and "start from zero" in out
    missing = build("nobody")
    ok = ok and "Run install.py" in missing and "SCHEDULED RUN" not in out
    os.environ.update(TEAM_RUN="1", TEAM_JOB="zed-morning")
    ok = ok and "SCHEDULED RUN (zed-morning)" in build("zed")
    del os.environ["TEAM_RUN"], os.environ["TEAM_JOB"]
    print("boot: ok" if ok else "boot: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    elif len(sys.argv) < 2:
        print(__doc__)
    else:
        print(build(sys.argv[1], dry="--dry" in sys.argv))
