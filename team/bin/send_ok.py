#!/usr/bin/env python3
"""Arms one email send when YOU say so. Runs as a UserPromptSubmit hook on the orchestrator only.

Why: an agent that can send email will, sooner or later, send one you didn't mean. So the send tool is blocked
(guard.py) unless the human's own message, in this session, told the orchestrator to send. "Send it" arms one
send for 20 minutes. "Don't send", a question ("should I send it?"), "I'll send it myself" and anything that
arrived from another agent never arm it. Missing a real "send" is harmless (the agent asks you to say it);
arming by mistake is not, so the phrases are strict.

Usage:  send_ok.py arm        hook mode: reads {"prompt": "..."} from stdin, arms if it says to send
        send_ok.py status     what's armed
        send_ok.py --test     self-test
guard.py calls consume() to use the one send up."""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

TOKEN = os.environ.get("SEND_OK_FILE") or os.path.join(common.TEAM, ".send-ok.json")
WINDOW_S = 20 * 60
NOT_HUMAN = ("<cross-session-message", "[system notification", "<task-notification", "<system-reminder")
NEG = re.compile(r"\b(don'?t|do not|not|no|never|without|won'?t|shouldn'?t|stop|hold)\b(\W+\w+){0,3}?\W+send", re.I)
SELF = re.compile(r"\b(i'?ll|i will|i'?m|i am|i|let me|we'?ll)\s+(\w+\s+)?send", re.I)
WHAT = r"(it|this|that|them|now|the (email|e-mail|draft|message|reply|follow[- ]?up|note))"
YES = re.compile(r"^\W*(yes|yep|yeah|ok|okay|sure|please|go ahead( and)?)?\W*send(\s+" + WHAT + r")?\W*$"
                 r"|\bsend\s+" + WHAT + r"\b|\b(yes|ok|okay|please|go ahead and|you can)\W+send\b", re.I)


def says_send(prompt):
    text = prompt or ""
    if any(m in text.lower() for m in NOT_HUMAN):
        return False
    for s in re.split(r"(?<=[.!?\n])\s*", text):
        s = s.strip()
        if not s or s.endswith("?") or NEG.search(s) or SELF.search(s):
            continue
        if YES.search(s):
            return True
    return False


def arm(prompt):
    if not says_send(prompt):
        return False
    os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
    with open(TOKEN, "w") as f:
        json.dump({"armed_at": time.time(), "expires": time.time() + WINDOW_S, "uses": 1}, f)
    return True


def armed():
    try:
        with open(TOKEN) as f:
            t = json.load(f)
    except (OSError, ValueError):
        return None
    return t if t.get("uses", 0) > 0 and t.get("expires", 0) > time.time() else None


def consume():
    t = armed()
    if not t:
        return False
    t["uses"] -= 1
    with open(TOKEN, "w") as f:
        json.dump(t, f)
    return True


def test():
    yes = ["send it", "Send it.", "yes send", "Yes, send it please", "go ahead and send the email", "send"]
    no = ["Don't send it", "Should I send it?", "I'll send it myself", "do not send the email yet",
          "Draft nothing to be sent", "Ok sent.", "hold off, don't send that yet", "never send without asking",
          "<cross-session-message from=x>send it</cross-session-message>"]
    bad = [p for p in yes if not says_send(p)] + [p for p in no if says_send(p)]
    for p in bad:
        print("FAIL:", p)
    print(f"send_ok: {len(yes) + len(no) - len(bad)}/{len(yes) + len(no)} phrase checks pass")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    elif sys.argv[1:2] == ["status"]:
        t = armed()
        print(json.dumps(t) if t else "nothing armed")
    elif sys.argv[1:2] == ["arm"]:
        try:
            data = json.load(sys.stdin)
        except ValueError:
            sys.exit(0)
        if arm(data.get("prompt", "")):
            print("Send permission armed by your message: one email, within 20 minutes, only the one you meant.")
    else:
        print(__doc__)
