#!/usr/bin/env python3
"""Open an intern: print its start-up context, then start your AI coding tool in its folder.

The tool is "tool" in team/team.json (install.py sets it to the first of claude, codex or gemini on your PATH). An
intern can use a different one: add "tool" to its agents/<name>/agent.json. Claude Code also loads the start-up
context itself through its hook; other tools read AGENTS.md, which tells them to run boot.py first.

Usage:  open.py <intern>            e.g. open.py theo
        open.py <intern> --print    the context and the command, without starting anything
        open.py --test"""
import json
import os
import shlex
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

BOOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boot.py")


def tool_for(agent):
    try:
        with open(os.path.join(common.agent_dir(agent), "agent.json")) as f:
            own = json.load(f).get("tool")
    except (OSError, ValueError):
        own = None
    return shlex.split(own or common.load_config().get("tool") or "claude")


def known(agent):
    return os.path.isfile(os.path.join(common.agent_dir(agent), "AGENT.md"))


def main(argv):
    names = [a for a in argv[1:] if not a.startswith("--")]
    if not names:
        print(__doc__)
        return 2
    agent = names[0].lower()
    if not known(agent):
        print(f"No intern called {agent}. The team: {', '.join(common.agent_names()) or 'run install.py first'}.")
        return 2
    folder, cmd = common.agent_dir(agent), tool_for(agent)
    boot = subprocess.run([sys.executable, BOOT, agent], capture_output=True, text=True)
    print(boot.stdout.strip() or boot.stderr.strip())
    print(f"\n--- starting {' '.join(cmd)} in agents/{os.path.basename(folder)} ---\n")
    if "--print" in argv:
        return 0
    if not shutil.which(cmd[0]):
        print(f"`{cmd[0]}` isn't on your PATH. Install your AI coding tool, or set \"tool\" in team/team.json.")
        return 1
    os.chdir(folder)
    os.environ["TEAM_AGENT"] = agent       # approvals.py refuses a sign-off from inside an intern's session
    os.execvp(cmd[0], cmd)


def test():
    import tempfile
    common.CONFIG = os.path.join(tempfile.mkdtemp(), "team.json")
    ok = tool_for("nobody") == ["claude"]
    with open(common.CONFIG, "w") as f:
        json.dump({"tool": "codex"}, f)
    ok &= tool_for("nobody") == ["codex"]
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        ok &= main(["open.py"]) == 2 and main(["open.py", "nobody-here"]) == 2
    print("open: ok" if ok else "open: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(test() if "--test" in sys.argv else main(sys.argv))
