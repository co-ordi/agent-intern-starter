#!/usr/bin/env python3
"""Set up your interns. Three questions, then they're ready; run it again any time to change an answer (it swaps the
old values for the new ones in the interns' files and never touches their memory).

What it does:
  1. Asks your first name, your business in one line and the goal they all serve (Enter skips it: the head intern
     asks on day one). The interns keep the names Theo, Ella, Chris and Arthur unless you want others, the timezone is
     your computer's, the AI tool is the first of claude, codex or gemini on your PATH, and Slack is left for later.
  2. Renames the agent folders if you renamed an intern, fills the {{placeholders}} in AGENT.md, OPERATING.md
     and the skills, and writes each intern's AGENTS.md (read by many AI coding tools) and CLAUDE.md (Claude Code's).
  3. Writes team/team.json (the team's config, gitignored) and the schedule with the new names.
  4. Puts a small launcher for each intern in bin/ (`bin/theo` opens the head intern, like team/bin/open.py theo).
  5. Keeps your interns' memory and working files out of git: checks .gitignore has the rules (adding any that are
     missing) and marks the memory files so git leaves them alone. Nothing for you to set up.

Then: `python3 team/bin/open.py theo`, and the head intern runs a short interview to fit the team to your business.

Usage:  python3 install.py                 three questions
        python3 install.py --yes [--owner "Sam" --business "..." --goal "..." --names Theo,Ella,Chris,Arthur
                           --timezone Europe/Paris --tool claude|codex|gemini --bigger-pieces "a weekly video"
                           --onboarded]
                                           no questions: the flags you give, defaults for the rest
        python3 install.py --yes --answers -    the same answers as JSON on stdin (or a file path instead of -),
                                           e.g. {"owner": "Sam", "business": "...", "goal": "...", "names": ["Theo", ...]},
                                           so no shell ever reads your words
        python3 install.py --dry-run       show what would change
        python3 install.py --help          this help (installs nothing)"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.join(ROOT, "agents")
TEAM = os.path.join(ROOT, "team")
CONFIG = os.path.join(TEAM, "team.json")
DEFAULT_NAMES = {"orchestrator": "Theo", "sales": "Ella", "marketing": "Chris", "finance": "Arthur"}
ROLE_ORDER = ["orchestrator", "sales", "marketing", "finance"]
ROLE_TITLE = {"orchestrator": "head intern, orchestrator", "sales": "sales", "marketing": "marketing", "finance": "finance"}
ROLE_PROMPT = {"orchestrator": "head intern (the orchestrator, who runs the others)", "sales": "sales intern",
               "marketing": "marketing intern", "finance": "finance intern"}
PRIVATE_RULES = ["agents/*/memory/*.md", "!agents/*/memory/MEMORY.md", "!agents/*/memory/questions.md",
                 "!agents/*/memory/log.md", "agents/*/out/", "team/inbox/*/", "team/logs/", "logs/", "team/team.json",
                 "**/.claude/settings.local.json", "team/.send-ok.json", "team/.approvals.json*", ".env", "*.key",
                 "*.pem", "/bin/"]
FILL_FILES = ("AGENT.md", "OPERATING.md", "PLAYBOOK.md")
RUNNERS = {"claude": "claude -p", "codex": "codex exec", "gemini": "gemini -p"}  # headless: the prompt goes last
BIGGER_DEFAULT = "one longer piece a month (an article, a video or an event)"


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}" + (f" [{default}]" if default else "") + ": ").strip()
    except EOFError:
        v = ""
    return v or default


def current():
    """Role -> folder name, from team.json if it exists, else from each folder's agent.json."""
    try:
        with open(CONFIG) as f:
            cfg = json.load(f)
        return {a["role"]: n for n, a in cfg["agents"].items()}, cfg
    except (OSError, ValueError, KeyError):
        pass
    roles = {}
    for d in sorted(os.listdir(AGENTS)):
        p = os.path.join(AGENTS, d, "agent.json")
        if os.path.isfile(p):
            with open(p) as f:
                roles[json.load(f)["role"]] = d
    return roles, {"timezone": detect_timezone(), "agents": {}}


def detect_timezone():
    """This computer's timezone as an IANA name (e.g. America/New_York), or UTC if it can't tell."""
    tz = os.environ.get("TZ", "").lstrip(":")
    if re.fullmatch(r"[A-Za-z]+(/[A-Za-z0-9_+-]+)+", tz or ""):
        return tz
    try:
        real = os.path.realpath("/etc/localtime")
        if "zoneinfo/" in real:
            return real.split("zoneinfo/", 1)[1]
    except OSError:
        pass
    try:
        with open("/etc/timezone") as f:
            name = f.read().strip()
        if name:
            return name
    except OSError:
        pass
    return "UTC"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "intern"


def detect_tool():
    """The first AI coding tool on your PATH, or claude if none is installed yet."""
    return next((t for t in RUNNERS if shutil.which(t)), "claude")


def flag(argv, name):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None


ANSWER_KEYS = ("owner", "business", "goal", "names", "timezone", "tool", "bigger_pieces")


def with_answers(argv, stdin=None):
    """Expand --answers FILE (or - for stdin) into the matching flags. Flags typed on the command line win."""
    src = flag(argv, "--answers")
    if src is None:
        return list(argv)
    if src == "-":
        data = json.load(stdin or sys.stdin)
    else:
        with open(src, encoding="utf-8") as fh:
            data = json.load(fh)
    if not isinstance(data, dict) or set(data) - set(ANSWER_KEYS):
        raise SystemExit(f"--answers takes a JSON object with only these keys: {', '.join(ANSWER_KEYS)}")
    extra = []
    for key in ANSWER_KEYS:
        if key in data and data[key] is not None:
            value = data[key]
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
            extra += ["--" + key.replace("_", "-"), str(value)]
    return list(argv) + extra


def gather(argv=(), ask_questions=True):
    roles, cfg = current()
    owner = cfg.get("owner", {})
    names = {r: cfg.get("agents", {}).get(roles.get(r, ""), {}).get("display") or DEFAULT_NAMES[r] for r in ROLE_ORDER}
    tool = flag(argv, "--tool") or cfg.get("tool") or detect_tool()
    answers = {"owner": flag(argv, "--owner") or owner.get("name") or "the founder",
               "business": flag(argv, "--business") or owner.get("business") or "a growing company",
               "goal": flag(argv, "--goal") if flag(argv, "--goal") is not None else owner.get("goal", ""),
               "timezone": flag(argv, "--timezone") or cfg.get("timezone") or detect_timezone(),
               "bigger_pieces": flag(argv, "--bigger-pieces") or owner.get("bigger_pieces") or BIGGER_DEFAULT,
               "tool": tool,
               "runner": (None if flag(argv, "--tool") else cfg.get("runner")) or RUNNERS.get(tool, tool + " -p")}
    if flag(argv, "--names"):
        given = [n.strip() for n in flag(argv, "--names").split(",")]
        names = {r: given[i] if i < len(given) and given[i] else names[r] for i, r in enumerate(ROLE_ORDER)}
    if not ask_questions:
        return answers, names
    print("Three questions. Press Enter to keep what's in brackets.\n")
    answers["owner"] = ask("Your first name", owner.get("name", ""))
    answers["business"] = ask("Your business, in one line", owner.get("business", ""))
    answers["goal"] = ask("The one goal they all serve this quarter (e.g. 'ten new clients'; Enter to let the head "
                          "intern ask you)", owner.get("goal", ""))
    keep = ask(f"Keep the names {', '.join(names.values())}? (y/n)", "y")
    if keep.lower().startswith("n"):
        names = {r: ask(f"Name for your {ROLE_PROMPT[r]}", names[r]) for r in ROLE_ORDER}
    print(f"\nTimezone: {answers['timezone']} (from your computer; --timezone changes it).")
    print(f"AI tool: {answers['tool']} (--tool claude, codex or gemini changes it).")
    print("Slack: skipped for now. Add it later: integrations/messaging.md.\n")
    return answers, names


def fill(text, answers, names, old_display, old_answers=None):
    """Fill the {{PLACEHOLDERS}} on the first run; on later runs, swap the previous answers for the new ones."""
    for key in ("owner", "business", "goal", "timezone", "bigger_pieces"):
        new = answers.get(key, "")
        if not new:
            continue  # left blank: keep the placeholder (or the old value) for you to fill in later
        text = text.replace("{{" + key.upper() + "}}", new)
        old = (old_answers or {}).get(key, "")
        if old and old != new:
            text = re.sub(r"(?<!\w)" + re.escape(old) + r"(?!\w)", lambda m: new, text)
    for role, new in names.items():
        old = old_display.get(role, DEFAULT_NAMES[role])
        if old != new:
            text = re.sub(rf"\b{re.escape(old)}\b", new, text)
            text = re.sub(rf"\b{re.escape(old.lower())}\b", slug(new), text)
    return text


def plan(answers, names):
    roles, cfg = current()
    old_display = {r: cfg["agents"].get(roles.get(r, ""), {}).get("display") or DEFAULT_NAMES[r] for r in ROLE_ORDER}
    steps = []
    for r in ROLE_ORDER:
        old_folder = roles.get(r) or slug(DEFAULT_NAMES[r])
        new_folder = slug(names[r])
        if old_folder != new_folder:
            steps.append(("rename", old_folder, new_folder))
        steps.append(("fill", new_folder, r))
    return steps, old_display


def apply(answers, names, dry=False):
    steps, old_display = plan(answers, names)
    _, prev = current()
    old_answers = dict(prev.get("owner", {}), timezone=prev.get("timezone", ""))
    old_answers = {"owner": old_answers.get("name", ""), "business": old_answers.get("business", ""),
                   "goal": old_answers.get("goal", ""), "timezone": old_answers.get("timezone", ""),
                   "bigger_pieces": old_answers.get("bigger_pieces", "")}
    cfg = {"timezone": answers["timezone"], "tool": answers.get("tool", "claude"),
           "runner": answers.get("runner", RUNNERS["claude"]),
           "owner": {"name": answers["owner"], "business": answers["business"], "goal": answers["goal"],
                     "bigger_pieces": answers.get("bigger_pieces", "")}, "agents": {}}
    for k in ("slack_channel", "slack_owner", "onboarded", "allow"):  # set later; a re-run keeps them
        if prev.get(k):
            cfg[k] = prev[k]
    if "--onboarded" in sys.argv:
        import datetime
        cfg["onboarded"] = datetime.date.today().isoformat()
    for kind, a, b in steps:
        if kind == "rename":
            print(f"rename agents/{a} -> agents/{b}")
            if not dry:
                shutil.move(os.path.join(AGENTS, a), os.path.join(AGENTS, b))
        else:
            folder, role = a, b
            home = os.path.join(AGENTS, folder)
            display = names[role]
            cfg["agents"][folder] = {"role": role, "display": display, "title": f"{display} · {ROLE_TITLE[role]}"}
            print(f"fill   agents/{folder} ({role}: {display})")
            if dry:
                continue
            targets = [os.path.join(home, f) for f in FILL_FILES]
            for sk_root, _, files in os.walk(os.path.join(home, ".claude")):
                targets += [os.path.join(sk_root, f) for f in files if f.endswith((".md", ".json"))]
            for p in targets:
                if os.path.isfile(p):
                    with open(p, encoding="utf-8") as f:
                        text = f.read()
                    new = fill(text, answers, names, old_display, old_answers)
                    if new != text:
                        with open(p, "w", encoding="utf-8") as f:
                            f.write(new)
            with open(os.path.join(home, "CLAUDE.md"), "w") as f:
                f.write(f"@AGENT.md\n\nYou are {display}. Your brief is AGENT.md above; how you operate is OPERATING.md; "
                        f"your defaults are PLAYBOOK.md. The start-up hook loads your memory and today's team notes.\n")
            with open(os.path.join(home, "AGENTS.md"), "w") as f:
                f.write(agents_md(folder, role, display))
            meta = {"name": folder, "role": role, "display": display}
            try:
                with open(os.path.join(home, "agent.json")) as f:
                    meta = dict(json.load(f), **meta)  # keeps anything you added, such as "tool"
            except (OSError, ValueError):
                pass
            with open(os.path.join(home, "agent.json"), "w") as f:
                json.dump(meta, f, indent=2)
    if dry:
        print("(dry run: nothing written)")
        return
    os.makedirs(TEAM, exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, indent=2)
    # schedule: swap old folder names for new ones
    sched = os.path.join(TEAM, "schedule.json")
    if os.path.isfile(sched):
        with open(sched) as f:
            text = f.read()
        for kind, a, b in steps:
            if kind == "rename":
                text = text.replace(f'"{a}"', f'"{b}"').replace(f'"{a}-', f'"{b}-')
        with open(sched, "w") as f:
            f.write(text)
    launchers(cfg)
    ensure_gitignore()
    protect_memory(cfg)
    print(f"\nDone. Next: python3 team/bin/open.py {slug(names['orchestrator'])}")
    print(f"The head intern interviews you for ten minutes and fits the team to your business"
          + (", starting with the goal." if not answers.get("goal") else "."))
    if not shutil.which(cfg["tool"]):
        print(f"Note: `{cfg['tool']}` isn't on your PATH yet. Install your AI coding tool, then the interns can start.")


def agents_md(folder, role, display):
    """AGENTS.md: the intern's brief for any AI coding tool (many read this file by convention). Claude Code reads
    CLAUDE.md, which points at the same brief, and also gets the hooks in .claude/settings.json."""
    text = (f"# {display} · {ROLE_TITLE[role]}\n\n"
            "This folder is one AI intern. Any AI coding tool that reads AGENTS.md can run it; Claude Code reads CLAUDE.md, "
            "which points at the same brief.\n\n"
            f"1. At the start of every session, run `python3 ../../team/bin/boot.py {folder}` and read what it prints: "
            "your memory, open questions, today's team notes and your orders. Never start from zero. (Claude Code runs "
            "it for you through the start-up hook.)\n"
            "2. Your brief is AGENT.md. How you operate is OPERATING.md. Your defaults, with their evidence, are PLAYBOOK.md. "
            "Read all three before answering.\n"
            "3. Your routines are the skills in `.claude/skills/<name>/SKILL.md`. When asked for one (\"run /brief\"), read "
            "that file and follow it.\n"
            f"4. The team guard decides on anything that could send, delete or expose a secret: `python3 ../../team/bin/guard.py {folder}`. "
            "Claude Code runs it before every tool call. If your tool has pre-command hooks, point them at it; if not, "
            "follow its rules as written in its docstring, and never send, delete or pay.\n"
            "5. Team rules: `../../team/TEAM.md`. They beat any order or skill.\n")
    if role == "orchestrator":
        text += ("\n## Day one: fit the team to the business\n\n"
                 "If `../../team/team.json` has no `\"onboarded\"` date, or the human asks to set up the team, run the "
                 "onboarding interview in `.claude/skills/onboard/SKILL.md` before anything else: about a dozen plain "
                 "questions, one at a time, a summary to confirm, then the interns' files filled in from the answers.\n")
    return text


def launchers(cfg):
    os.makedirs(os.path.join(ROOT, "bin"), exist_ok=True)
    for folder in cfg["agents"]:
        p = os.path.join(ROOT, "bin", folder)
        with open(p, "w") as f:
            f.write(f'#!/bin/sh\nexec python3 "{os.path.join(TEAM, "bin", "open.py")}" {folder} "$@"\n')
        os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP)


def ensure_gitignore(path=None):
    """Make sure .gitignore keeps memory, working files, config and keys out of git. Adds only the missing rules."""
    path = path or os.path.join(ROOT, ".gitignore")
    have = set()
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            have = {line.strip() for line in f}
    missing = [r for r in PRIVATE_RULES if r not in have]
    if missing:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n# Added by install.py: your interns' private files never go in git.\n" + "\n".join(missing) + "\n")
    return missing


def protect_memory(cfg):
    """Tell git to ignore local changes to the memory templates, so an intern's memory never ends up in a commit."""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        return
    paths = [f"agents/{a}/memory/{f}" for a in cfg["agents"] for f in ("MEMORY.md", "questions.md", "log.md")]
    paths += [f"agents/{a}/{f}" for a in cfg["agents"] for f in ("CLAUDE.md", "AGENTS.md", "agent.json")]
    subprocess.run(["git", "update-index", "--skip-worktree", "--"] + [p for p in paths if os.path.exists(os.path.join(ROOT, p))],
                   cwd=ROOT, capture_output=True)


if __name__ == "__main__":
    if "-h" in sys.argv or "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)
    sys.argv = with_answers(sys.argv)
    dry = "--dry-run" in sys.argv
    quiet = dry or "--yes" in sys.argv or "--defaults" in sys.argv or not sys.stdin.isatty()
    a, n = gather(sys.argv, ask_questions=not quiet)
    apply(a, n, dry=dry)
