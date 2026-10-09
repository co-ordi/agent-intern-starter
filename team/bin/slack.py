#!/usr/bin/env python3
"""The team's messaging script, for Slack: post a message or card, read replies, read reactions. Stdlib only.

These three calls are all the team needs from a channel. To use Teams, Discord, Telegram or email instead, write a
file with the same three functions (post, inbox, reactions) against that channel's API; approvals.py and the
interns' skills call them by name and don't care what's underneath.

Set-up (once):
  - A Slack app in your own workspace with a bot token and the scopes chat:write, reactions:read,
    channels:history and groups:history (the last one for a private channel). Invite the bot to one private channel.
  - The token: the TEAM_SLACK_TOKEN environment variable, or your macOS keychain
    (`security add-generic-password -s agent-interns-slack -a team -w`, which prompts for it).
  - In team/team.json: "slack_channel" (the channel id, C...) and "slack_owner" (your Slack user id, U...). Only
    your own reactions count as a sign-off.

Usage:  slack.py post --text "..." [--thread TS] [--dry]     prints the new message's ts
        slack.py inbox [--since TS] [--dry]                  your messages and thread replies since TS, as JSON lines
        slack.py reactions --ts TS [--dry]                   reactions on one message, as JSON
        slack.py --test
--dry prints the request instead of sending it, so you can try everything before the token exists."""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

API = "https://slack.com/api/"
KEYCHAIN_SERVICE = "agent-interns-slack"


class SlackError(Exception):
    pass


def token():
    t = os.environ.get("TEAM_SLACK_TOKEN", "").strip()
    if t:
        return t
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    raise SlackError("No Slack token: set TEAM_SLACK_TOKEN or add it to the keychain (see the top of slack.py).")


def channel():
    c = common.load_config().get("slack_channel", "")
    if not c:
        raise SlackError('No channel: add "slack_channel" to team/team.json.')
    return c


def owner():
    return common.load_config().get("slack_owner", "")


def call(method, params, dry=False, opener=None):
    """One Slack Web API call, form-encoded. Returns the parsed reply; raises SlackError if Slack says no."""
    if dry:
        print(json.dumps({"method": method, "params": params}))
        return {"ok": True, "ts": "dry", "messages": [], "message": {"reactions": []}}
    body = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")}).encode()
    req = urllib.request.Request(API + method, data=body, headers={
        "Authorization": "Bearer " + token(), "Content-Type": "application/x-www-form-urlencoded; charset=utf-8"})
    with (opener or urllib.request.urlopen)(req, timeout=20) as r:
        reply = json.loads(r.read().decode())
    if not reply.get("ok"):
        raise SlackError(f"{method}: {reply.get('error', 'unknown error')}")
    return reply


def post(text, thread=None, dry=False, opener=None):
    """Post to the team channel (or a thread in it). Returns the message ts."""
    return call("chat.postMessage", {"channel": channel(), "text": text, "thread_ts": thread,
                                     "unfurl_links": "false"}, dry, opener).get("ts", "")


def inbox(since="0", dry=False, opener=None):
    """Human messages in the channel since `since`, plus replies in their threads. Bots' own posts are left out."""
    c = channel()
    top = call("conversations.history", {"channel": c, "oldest": since, "limit": 100}, dry, opener).get("messages", [])
    out = []
    for m in top:
        if not m.get("bot_id"):
            out.append({"ts": m.get("ts"), "user": m.get("user"), "text": m.get("text", ""), "thread": None})
        if m.get("reply_count"):
            for r in call("conversations.replies", {"channel": c, "ts": m["ts"], "oldest": since}, dry, opener).get("messages", [])[1:]:
                if not r.get("bot_id"):
                    out.append({"ts": r.get("ts"), "user": r.get("user"), "text": r.get("text", ""), "thread": m["ts"]})
    return sorted(out, key=lambda m: float(m["ts"] or 0))


def reactions(ts, dry=False, opener=None):
    """[{"name": "+1", "users": [...]}] on one message."""
    msg = call("reactions.get", {"channel": channel(), "timestamp": ts, "full": "true"}, dry, opener).get("message", {})
    return [{"name": r.get("name"), "users": r.get("users", [])} for r in msg.get("reactions", [])]


def approved_by_owner(ts, opener=None):
    """True when your 👍 is on the message. With no slack_owner set, any human's 👍 counts (one private channel)."""
    who = owner()
    for r in reactions(ts, opener=opener):
        if r["name"] in ("+1", "thumbsup") and (not who or who in r["users"]):
            return True
    return False


def test():
    import io
    import tempfile
    common.CONFIG = os.path.join(tempfile.mkdtemp(), "team.json")
    with open(common.CONFIG, "w") as f:
        json.dump({"slack_channel": "C123", "slack_owner": "U1"}, f)
    os.environ["TEAM_SLACK_TOKEN"] = "test-token"
    seen = []

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=0):
        method = req.full_url.rsplit("/", 1)[1]
        params = dict(urllib.parse.parse_qsl(req.data.decode()))
        seen.append((method, params, req.get_header("Authorization")))
        replies = {
            "chat.postMessage": {"ok": True, "ts": "111.1"},
            "conversations.history": {"ok": True, "messages": [
                {"ts": "200.1", "user": "U1", "text": "hold until Monday", "reply_count": 1},
                {"ts": "201.1", "bot_id": "B1", "text": "card"}]},
            "conversations.replies": {"ok": True, "messages": [{"ts": "200.1"}, {"ts": "200.2", "user": "U1", "text": "shorter"}]},
            "reactions.get": {"ok": True, "message": {"reactions": [{"name": "+1", "users": ["U1"]}, {"name": "eyes", "users": ["U2"]}]}},
        }
        return Reply(json.dumps(replies.get(method, {"ok": False, "error": "unknown_method"})).encode())

    ok = post("Morning report", opener=fake) == "111.1"
    ok &= seen[0][0] == "chat.postMessage" and seen[0][1]["channel"] == "C123" and seen[0][2] == "Bearer test-token"
    msgs = inbox("100", opener=fake)
    ok &= [m["text"] for m in msgs] == ["hold until Monday", "shorter"] and msgs[1]["thread"] == "200.1"
    ok &= approved_by_owner("111.1", opener=fake)
    with open(common.CONFIG, "w") as f:
        json.dump({"slack_channel": "C123", "slack_owner": "U9"}, f)
    ok &= not approved_by_owner("111.1", opener=fake)  # someone else's 👍 doesn't count
    try:
        call("nope", {}, opener=fake)
        ok = False
    except SlackError:
        pass
    print("slack: ok" if ok else "slack: FAIL")
    sys.exit(0 if ok else 1)


def main(argv):
    dry = "--dry" in argv

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

    cmd = argv[1] if len(argv) > 1 else ""
    try:
        if cmd == "post" and opt("--text"):
            print(post(opt("--text"), opt("--thread"), dry))
        elif cmd == "inbox":
            for m in inbox(opt("--since", "0"), dry):
                print(json.dumps(m))
        elif cmd == "reactions" and opt("--ts"):
            print(json.dumps(reactions(opt("--ts"), dry)))
        else:
            print(__doc__)
            return 2
    except SlackError as e:
        print(f"slack: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    sys.exit(main(sys.argv))
