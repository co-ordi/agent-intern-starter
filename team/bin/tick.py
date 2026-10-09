#!/usr/bin/env python3
"""The scheduler. Runs the interns' routine jobs headlessly, from team/schedule.json, once a minute from cron.

A job is {"id": "ella-morning", "agent": "ella", "at": "08:15", "days": "Mon-Fri", "prompt": "/today",
"timeout_min": 15}, plus an optional "model" for simple jobs on a smaller model. On each tick, any job whose time
has come (and hasn't run today) starts headlessly in that agent's folder with the runner in team/team.json
("runner": "claude -p" by default; "codex exec" or "gemini -p" for those tools; the prompt goes last, and a job's
model goes in as --model, which Claude Code and Gemini CLI both take). TEAM_RUN=1 tells guard.py to apply the
scheduled-run rules. Output goes to team/logs/<job>.log; a one-line status to team/status/<job>.json so the
orchestrator's health check can see what ran, what failed and what was missed.

Each tick also checks the sign-off queue (approvals.py): it reads your reactions on draft cards (if a channel is
wired) and, for every card past its 2-minute undo, starts one short send run as the orchestrator. That run verifies
the draft against the card, locks it and sends it by draft id alone; guard.py lets nothing else through. Send runs
only start when the runner is Claude Code, whose hooks run the guard; with another tool the approved card waits and
the morning report lists it for you to send yourself.

cron line (every minute):
  * * * * *  cd /path/to/agent-intern-starter && mkdir -p team/logs && python3 team/bin/tick.py >> team/logs/tick.log 2>&1

Usage:  tick.py              run what's due now
        tick.py --list       show the schedule with the next run of each job
        tick.py --run ID     run one job now, whatever the time
        tick.py --dry        say what would run, without running
        tick.py --test"""
import datetime
import json
import os
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SCHEDULE = os.path.join(common.TEAM, "schedule.json")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_schedule(path=None):
    try:
        with open(path or SCHEDULE) as f:
            return json.load(f).get("jobs", [])
    except (OSError, ValueError):
        return []


def day_matches(spec, weekday):
    """'Mon-Fri', 'Sat', 'Mon,Wed,Fri' or 'daily' against a weekday index (Mon=0)."""
    spec = (spec or "daily").strip()
    if spec.lower() == "daily":
        return True
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            i, j = DAYS.index(a[:3].title()), DAYS.index(b[:3].title())
            rng = range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1))
            if weekday in rng:
                return True
        elif part and DAYS.index(part[:3].title()) == weekday:
            return True
    return False


def due(job, when, ran_today):
    hh, mm = map(int, job["at"].split(":"))
    return (day_matches(job.get("days"), when.weekday()) and (when.hour, when.minute) >= (hh, mm)
            and job["id"] not in ran_today)


def status_path(job_id):
    return os.path.join(common.STATUS, f"{job_id}.json")


def ran_today(when):
    out = set()
    for name in os.listdir(common.STATUS) if os.path.isdir(common.STATUS) else []:
        if name.endswith(".json"):
            try:
                with open(os.path.join(common.STATUS, name)) as f:
                    s = json.load(f)
                if s.get("date") == when.date().isoformat():
                    out.add(name[:-5])
            except (OSError, ValueError):
                pass
    return out


def runner():
    return shlex.split(common.load_config().get("runner") or "claude -p")


# What a scheduled run may do without asking, beyond editing inside its own folder and team/: the team scripts,
# its own tools, and the read and draft tools the interview added to "allow" in team.json. The guard still has
# the last word on every call.
ALLOW = ["Bash(python3 ../../team/bin/*)", "Bash(python3 tools/*)"]


def command(job):
    """The headless command for a job: the runner, its flags after the tool's name, the prompt last.
    Nobody is there to answer a permission prompt, so Claude Code gets team/ and its allowed tools up front."""
    r = runner()
    flags = ["--model", job["model"]] if job.get("model") else []
    if guarded():
        tools = ALLOW + common.load_config().get("allow", []) + job.get("tools", [])
        if job["agent"] == common.orchestrator():   # the head intern reads everyone's folder, writes only its own
            tools.append(f"Read(/{common.AGENTS}/**)")
        flags += ["--add-dir", common.TEAM, "--permission-mode", "acceptEdits", "--allowedTools", ",".join(tools)]
    return r[:1] + flags + r[1:] + [job["prompt"]]


def guarded():
    """Send runs need the guard as a hook, which only Claude Code runs today."""
    return os.path.basename(runner()[0]) == "claude"


def run_job(job, when, dry=False):
    folder = common.agent_dir(job["agent"])
    os.makedirs(common.LOGS, exist_ok=True)
    os.makedirs(common.STATUS, exist_ok=True)
    if dry:
        return f"would run {job['id']} ({job['agent']}: {job['prompt']})"
    env = dict(os.environ, TEAM_RUN="1", TEAM_JOB=job["id"], TEAM_AGENT=job["agent"])
    log = open(os.path.join(common.LOGS, f"{job['id']}.log"), "a")
    log.write(f"\n=== {when:%Y-%m-%d %H:%M} {job['id']} ===\n")
    log.flush()
    status = {"job": job["id"], "agent": job["agent"], "date": when.date().isoformat(), "started": f"{when:%H:%M}"}
    try:
        cmd = command(job)
        r = subprocess.run(cmd, cwd=folder, env=env, stdout=log, stderr=log,
                           timeout=60 * int(job.get("timeout_min", 15)))
        status["ok"] = r.returncode == 0
        status["exit"] = r.returncode
    except subprocess.TimeoutExpired:
        status["ok"] = False
        status["exit"] = "timeout"
    except FileNotFoundError:
        status["ok"] = False
        status["exit"] = f"{command(job)[0]} not found on PATH"
    finally:
        log.close()
    with open(status_path(job["id"]), "w") as f:
        json.dump(status, f)
    return f"{job['id']}: {'ok' if status['ok'] else status['exit']}"


SEND_PROMPT = (
    "Send run for an approved card (card {card}, draft {draft}, to {to}). Do exactly these steps and nothing else:\n"
    "1. Fetch draft {draft} with your mail tool and write its plain-text body to out/send-{card}.txt.\n"
    "2. Run `python3 ../../team/bin/approvals.py verify --card {card} --to \"<the draft's to>\" --cc \"<its cc>\" "
    "--subject \"<its subject>\" --body-file out/send-{card}.txt`. If it doesn't print ok, stop.\n"
    "3. Run `python3 ../../team/bin/approvals.py lock --card {card}`. If it doesn't print locked, stop.\n"
    "4. Send the draft with ONLY its draft id ({draft}), no other fields.\n"
    "5. Run `python3 ../../team/bin/approvals.py done --card {card}`, or add `--failed \"<why>\"` if step 4 failed.")
SENDS = os.path.join(common.STATUS, "sends.json")


def sends(when, dry=False, runner=None):
    """Read sign-offs and start one send run per card that's ready. Never twice for the same card within 10 minutes."""
    import approvals
    reacted = None
    if common.load_config().get("slack_channel"):
        import slack
        reacted = slack.approved_by_owner
    try:
        ready = approvals.tick(reacted)
    except Exception as e:  # the channel is down: still send what you approved from the terminal
        common.log_line(os.path.join(common.LOGS, "tick.log"), f"reading sign-offs failed: {e}")
        ready = approvals.tick(None)
    try:
        with open(SENDS) as f:
            started = json.load(f)
    except (OSError, ValueError):
        started = {}
    out = []
    if ready and not guarded():
        common.log_line(os.path.join(common.LOGS, "tick.log"), f"{len(ready)} signed-off card(s) waiting: send runs "
                        "need Claude Code's guard hook, so send them yourself")
        return [f"waiting for you: card {c['card']}" for c in ready]
    for c in ready:
        if when.timestamp() - started.get(c["card"], 0) < 600:
            continue
        job = {"id": f"send-{c['card']}", "agent": common.orchestrator(), "timeout_min": 5,
               "prompt": SEND_PROMPT.format(card=c["card"], draft=c["draft_id"], to=c["to"])}
        out.append((runner or run_job)(job, when, dry=dry))
        if not dry:
            started[c["card"]] = when.timestamp()
    if out and not dry:
        os.makedirs(common.STATUS, exist_ok=True)
        with open(SENDS, "w") as f:
            json.dump(started, f)
    return out


def next_run(job, when):
    for d in range(8):
        day = when + datetime.timedelta(days=d)
        hh, mm = map(int, job["at"].split(":"))
        t = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if day_matches(job.get("days"), day.weekday()) and t > when:
            return t
    return None


def main(argv):
    when = common.now()
    jobs = load_schedule()
    if "--list" in argv:
        for j in jobs:
            n = next_run(j, when)
            print(f"{j['id']:<22} {j['agent']:<10} {j['at']} {j.get('days', 'daily'):<8} next {n:%a %H:%M}" if n else j["id"])
        return
    if "--run" in argv:
        jid = argv[argv.index("--run") + 1]
        job = next((j for j in jobs if j["id"] == jid), None)
        print(run_job(job, when) if job else f"no job {jid}")
        return
    for line in sends(when, dry="--dry" in argv):
        print(line)
    done = ran_today(when)
    for j in jobs:
        if due(j, when, done):
            print(run_job(j, when, dry="--dry" in argv))


def test():
    import tempfile
    common.STATUS = tempfile.mkdtemp()
    common.CONFIG = os.path.join(tempfile.mkdtemp(), "team.json")   # no config: the default runner
    job = {"id": "x-morning", "agent": "x", "at": "08:15", "days": "Mon-Fri", "prompt": "/today"}
    mon_9 = datetime.datetime(2026, 1, 5, 9, 0)
    sat_9 = datetime.datetime(2026, 1, 10, 9, 0)
    mon_8 = datetime.datetime(2026, 1, 5, 8, 0)
    ok = due(job, mon_9, set()) and not due(job, sat_9, set()) and not due(job, mon_8, set())
    ok = ok and not due(job, mon_9, {"x-morning"})
    ok = ok and day_matches("Sat", 5) and day_matches("Fri-Mon", 6) and not day_matches("Mon,Wed", 1)
    ok = ok and next_run(job, sat_9).weekday() == 0
    # an approved card past its undo starts one send run as the orchestrator, and only once
    import time
    import approvals
    global SENDS
    SENDS = os.path.join(common.STATUS, "sends.json")
    approvals.STATE = os.path.join(tempfile.mkdtemp(), "a.json")
    common.INBOX = tempfile.mkdtemp()
    approvals._test_keys = approvals.test_keys()   # stand in for your sign-off keys
    cid = approvals.card("ella", "d1", "a@b.com", "Hi", "Body")
    approvals.approve(cid, answer=lambda code: code, at=time.time() - approvals.DELAY_S - 1)
    calls = []
    runner = lambda job, when, dry=False: calls.append(job) or job["id"]  # noqa: E731
    now = datetime.datetime.now()
    ok = ok and sends(now, runner=runner) == [f"send-{cid}"] and sends(now, runner=runner) == []
    ok = ok and calls[0]["agent"] == common.orchestrator() and "lock --card " + cid in calls[0]["prompt"]
    # the runner comes from team.json; the model goes after the tool's name, the prompt last
    with open(common.CONFIG, "w") as f:
        json.dump({"allow": ["mcp__mail__create_draft"]}, f)
    c = command(dict(job, model="small", tools=["WebSearch"]))
    ok = ok and c[:3] == ["claude", "--model", "small"] and c[-2:] == ["-p", "/today"]
    # scheduled runs can write team notes and run the team scripts, with nobody there to click allow
    ok = ok and c[c.index("--add-dir") + 1] == common.TEAM and c[c.index("--permission-mode") + 1] == "acceptEdits"
    ok = ok and c[c.index("--allowedTools") + 1].split(",") == ALLOW + ["mcp__mail__create_draft", "WebSearch"]
    o = command(dict(job, agent=common.orchestrator()))
    ok = ok and o[o.index("--allowedTools") + 1].endswith(f",Read(/{common.AGENTS}/**)")
    for run, want in (("codex exec", ["codex", "exec", "/today"]), ("gemini -p", ["gemini", "-p", "/today"])):
        with open(common.CONFIG, "w") as f:
            json.dump({"runner": run}, f)
        ok = ok and command(job) == want and not guarded()
    # without the guard hook, a signed-off card waits for you instead of starting a send run
    c2 = approvals.card("ella", "d2", "a@b.com", "Hi", "Body")
    approvals.approve(c2, answer=lambda code: code, at=time.time() - approvals.DELAY_S - 1)
    approvals._test_keys = None
    calls.clear()
    ok = ok and f"waiting for you: card {c2}" in sends(now, runner=runner) and calls == []
    print("tick: ok" if ok else "tick: FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    test() if "--test" in sys.argv else main(sys.argv[1:])
