#!/usr/bin/env python3
"""Your sign-off, then one send. Every email an intern drafts for someone outside the company becomes a draft card,
and nothing goes out any other way.

The flow:
  1. An intern writes the email as a draft in your mail client, then runs `approvals.py card` with the exact text.
     The card goes to your private channel (slack.py, or your own messaging script with the same three calls), or,
     with no channel, to team/inbox/<date>/cards.md for you to read. The draft is the master copy; the card shows
     what it says.
  2. You approve: a 👍 on the card in the channel, or `approvals.py approve --card C` typed in your own terminal
     (it shows a fresh code to type back, and on macOS your Mac asks for your password before it signs).
     Nothing happens for 2 minutes; remove the reaction (or run `approve --off`) and it's cancelled.
  3. The orchestrator's run calls `tick`, which reads the reactions and lists the cards that are ready. For each one
     it fetches the draft, runs `verify` (the draft must still match the card: to, cc, subject, body), then `lock`,
     then sends with ONLY the draft id, then `done`. guard.py lets that send through only for a locked card past its
     2 minutes, once; any other send from a scheduled run is blocked.
  4. You change a draft by replying in the card's thread. The intern updates the same draft and posts a new version
     with `card --card C`; a sign-off on an older version doesn't count.

Agents can't approve on your behalf, and the code checks it rather than trusting it:
  - Every sign-off carries evidence. A channel sign-off is re-checked live at send time (your reaction must still be
    on the card, from your own account). A terminal sign-off carries an RSA signature (openssl). The private key
    lives in your macOS keychain with no trusted apps, so every read asks for your Mac password (click Allow, never
    Always Allow); the public half (~/.config/agent-interns/signoff.pub) is all the send run needs, so scheduled
    sends never wait on a prompt. Off macOS the private key is a file only your user can read, encrypted with a
    passphrase you choose at your first sign-off and type at every one after, so a script that reads the file gets
    nothing it can sign with.
  - `approve` only works in your own terminal: it needs an interactive terminal, refuses to run inside an AI tool
    (TEAM_AGENT, TEAM_RUN, CLAUDECODE and similar markers), and asks you to type back a code it shows only there.
    No code is written to the card, cards.md or the state file.
  - `lock` needs a passing `verify` of the current draft, and the guard blocks edits to a draft once you've signed it off.
  - guard.py blocks interns from reacting in your channel, running `approve`, importing or globbing for this module,
    faking a terminal (script, expect, pty), stripping the AI-tool markers (env -u), and touching the keys.
A typed "send" in the channel isn't a sign-off either. Known limits are in AGENTS.md: an intern runs as your user
account, so deliberately obfuscated code could reach what you can; for hard isolation, run the interns under a
separate OS user or in a container.

Usage:  approvals.py card --as AGENT --draft-id ID --to a@b.com [--cc c@d.com] --subject S --body-file F [--card C] [--dry]
        approvals.py approve --card C [--off]      your sign-off, in your own terminal only
        approvals.py tick [--dry]                  read reactions, start or cancel the clocks, print ready cards as JSON
        approvals.py verify --card C --to ... [--cc ...] --subject ... --body-file F
        approvals.py lock --card C
        approvals.py done --card C [--failed "why"]
        approvals.py list
        approvals.py --test"""
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DELAY_S = 120  # the undo window: a constant on purpose, so no prompt or flag can shorten it
STATE = os.environ.get("APPROVALS_FILE") or os.path.join(common.TEAM, ".approvals.json")
OPEN = ("waiting", "clock")
SIGNED = ("clock", "locked", "sending")
KEY_SERVICE = "agent-interns-signing-key"   # the guard blocks any intern command that mentions agent-interns
KEY_DIR = os.path.join(os.path.expanduser("~"), ".config", "agent-interns")
KEY_FILE = os.path.join(KEY_DIR, "signoff.key")   # the private key, off macOS only, encrypted with your passphrase
PUB_FILE = os.path.join(KEY_DIR, "signoff.pub")   # the public half: checks a signature, can't make one
AGENT_MARKERS = ("TEAM_AGENT", "TEAM_RUN", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX",
                 "CODEX_MANAGED_BY_NPM", "GEMINI_CLI", "CURSOR_TRACE_ID")
_test_keys = None  # (private PEM, public PEM), set only by the self-tests


def _load():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, STATE)


def _openssl(*args, stdin=None):
    exe = shutil.which("openssl")
    if not exe:
        return None
    r = subprocess.run([exe, *args], input=stdin, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def test_keys():
    """A throwaway key pair for the self-tests."""
    priv = _openssl("genrsa", "2048")
    return priv, _openssl("rsa", "-pubout", stdin=priv)


def _on_keychain():
    return sys.platform == "darwin" and bool(shutil.which("security"))


def _with_key_file(priv, fn):
    """Run fn(path) with the key in a temporary file only your user can read (it's encrypted off macOS)."""
    with tempfile.TemporaryDirectory() as d:
        k = os.path.join(d, "k")
        fd = os.open(k, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(priv)
        return fn(d, k)


def _private_key(create=False, passphrase=None):
    """The key that makes terminal sign-offs. macOS: your login keychain, created with an empty trusted-apps list
    (-T ""), so every read asks for your Mac password. Elsewhere: a file only your user can read, encrypted with
    your passphrase (AES-256, PKCS#8), which you type at each sign-off. An older unencrypted key file is replaced."""
    if _test_keys:
        return _test_keys[0]
    if _on_keychain():
        r = subprocess.run(["security", "find-generic-password", "-s", KEY_SERVICE, "-a", "interns", "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return base64.b64decode(r.stdout.strip())
    else:
        try:
            with open(KEY_FILE, "rb") as f:
                data = f.read()
            if b"ENCRYPTED" in data:
                return data
        except OSError:
            pass
    if not create:
        return None
    if _on_keychain():
        priv = _openssl("genrsa", "2048")
        pub = priv and _openssl("rsa", "-pubout", stdin=priv)
    else:
        if not passphrase:
            return None
        pw = (passphrase + "\n").encode()
        priv = _openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-aes-256-cbc",
                        "-pass", "stdin", stdin=pw)
        pub = priv and _with_key_file(priv, lambda d, k: _openssl("pkey", "-in", k, "-passin", "stdin", "-pubout",
                                                                   stdin=pw))
    if not pub:
        return None
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    if _on_keychain():
        r = subprocess.run(["security", "add-generic-password", "-s", KEY_SERVICE, "-a", "interns", "-T", "",
                            "-w", base64.b64encode(priv).decode()], capture_output=True)
        if r.returncode != 0:
            return None
    else:
        fd = os.open(KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(priv)
    with open(PUB_FILE, "wb") as f:
        f.write(pub)
    return priv


def _public_key():
    if _test_keys:
        return _test_keys[1]
    try:
        with open(PUB_FILE, "rb") as f:
            return f.read() or None
    except OSError:
        return None


def _message(cid, c):
    return f"{cid}|{c['fp']}|{c['version']}|{c['thumbed_at']}".encode()


def _sign(priv, msg, passphrase=None):
    """A signature over msg, or "" if the key can't be used (an encrypted key with no passphrase, or the wrong one)."""
    def run(d, k):
        m = os.path.join(d, "m")
        with open(m, "wb") as f:
            f.write(msg)
        if b"ENCRYPTED" in priv:   # the passphrase goes on stdin, never on the command line
            return _openssl("dgst", "-sha256", "-sign", k, "-passin", "stdin", m, stdin=((passphrase or "") + "\n").encode())
        return _openssl("dgst", "-sha256", "-sign", k, m)
    sig = _with_key_file(priv, run)
    return sig.hex() if sig else ""


def _signature_ok(cid, c):
    pub, sig = _public_key(), c.get("sig") or ""
    if not pub or not re.fullmatch(r"[0-9a-f]{64,}", sig):
        return False
    with tempfile.TemporaryDirectory() as d:
        paths = {n: os.path.join(d, n) for n in ("m", "s", "p")}
        for n, data in (("m", _message(cid, c)), ("s", bytes.fromhex(sig)), ("p", pub)):
            with open(paths[n], "wb") as f:
                f.write(data)
        return _openssl("dgst", "-sha256", "-verify", paths["p"], "-signature", paths["s"], paths["m"]) is not None


def under_agent():
    """True inside an AI coding tool or a scheduled run (open.py and tick.py set TEAM_AGENT / TEAM_RUN)."""
    return any(os.environ.get(k) for k in AGENT_MARKERS)


def human_terminal():
    return sys.stdin.isatty() and sys.stdout.isatty() and not under_agent()


def fingerprint(to, cc, subject, body):
    norm = lambda t: re.sub(r"\s+", " ", (t or "").strip().lower())  # noqa: E731
    return hashlib.sha256("|".join([norm(to), norm(cc), norm(subject), norm(body)]).encode()).hexdigest()[:16]


def card_text(c, body):
    head = (f"Draft from {c['agent']} · version {c['version']}\nTo: {c['to']}"
            + (f"\nCc: {c['cc']}" if c["cc"] else ""))
    return (f"{head}\nSubject: {c['subject']}\n\n{body}\n\n"
            "React with a thumbs up to send it (2 minutes to change your mind: remove the reaction to cancel). "
            "Reply in this thread to change it.")


def card(agent, draft_id, to, subject, body, cc="", card_id=None, poster=None):
    """Register a card (new, or a new version of card_id) and show it to the human. Returns the card id."""
    s = _load()
    cid = card_id
    if not cid:
        n = int(time.time() * 1000)
        while f"c{n}" in s:  # two cards in the same millisecond
            n += 1
        cid = f"c{n}"
    c = {"agent": agent, "draft_id": draft_id, "to": to, "cc": cc, "subject": subject,
         "fp": fingerprint(to, cc, subject, body), "version": s.get(cid, {}).get("version", 0) + 1,
         "state": "waiting", "thumbed_at": None, "ts": None}
    text = card_text(c, body)
    if poster:
        c["ts"] = poster(text)
    else:
        path = os.path.join(common.INBOX, common.today(), "cards.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n## Card {cid}\n\n{text}\n")
    s[cid] = c
    _save(s)
    return cid


def _record(cid, up=True, at=None, via="channel", sign=None):
    """Record a sign-off (or its withdrawal) on the latest version of a card. Internal: the evidence it stores is what
    send_allowed() checks, so writing this by hand gets nothing sent. sign(message) -> signature, terminal only."""
    s = _load()
    c = s.get(cid)
    if not c or c["state"] not in OPEN:
        return False
    if up and c["state"] == "clock":
        return True  # already counting down: keep the first time
    c["thumbed_at"] = (at or time.time()) if up else None
    c["state"] = "clock" if up else "waiting"
    c["via"] = via if up else None
    c["sig"] = None
    c.pop("verified_fp", None)
    if up and via == "terminal" and sign:
        c["sig"] = sign(_message(cid, c))
    _save(s)
    return True


def _ask_passphrase(new):
    import getpass
    if not new:
        return getpass.getpass("Your sign-off passphrase: ")
    print("First sign-off on this computer: choose a passphrase (12 characters or more; four random words is good).\n"
          "You'll type it at every sign-off. It never leaves this computer, and nobody can recover it.")
    first = getpass.getpass("New sign-off passphrase: ")
    if len(first) < 12 or getpass.getpass("Once more: ") != first:
        return None
    return first


def approve(cid, up=True, answer=None, at=None, passphrase=None):
    """Your sign-off from your own terminal. Refuses inside an AI tool or without an interactive terminal, shows a
    fresh code you type back (answer(code) stands in for you in the tests), then signs with your private key, which
    on macOS asks for your Mac password and elsewhere for your sign-off passphrase (passphrase(new) stands in)."""
    if not (human_terminal() or _test_keys):
        return "refused: sign-offs only come from your own terminal (or your reaction on the card), never an intern"
    c = _load().get(cid)
    if not c:
        return "no open card with that id"
    if not up:
        return "ok" if _record(cid, False) else "no open card with that id"
    code = secrets.token_hex(2)
    ask = answer or (lambda shown: input(f"Send '{c['subject']}' to {c['to']}? Type {shown} to confirm: "))
    if ask(code).strip().lower() != code:
        return "refused: the code didn't match"
    pw = None
    if not (_test_keys or _on_keychain()):
        existing = _private_key()
        pw = (passphrase or _ask_passphrase)(not existing)
        if not pw:
            return "refused: no passphrase (12 characters or more, typed the same twice)"
        priv = existing or _private_key(create=True, passphrase=pw)
    else:
        priv = _private_key(create=True)
    if not priv:
        return "refused: no signing key (it needs openssl; on a Mac, click Allow when it asks for your password)"
    if not _sign(priv, b"check", pw):
        return "refused: that passphrase doesn't open your sign-off key"
    return "ok" if _record(cid, True, at=at, via="terminal", sign=lambda m: _sign(priv, m, pw)) else "no open card with that id"


def ready(now=None):
    """Cards whose 2 minutes have passed and that still carry the sign-off."""
    now = now or time.time()
    return [cid for cid, c in _load().items() if c["state"] == "clock" and c["thumbed_at"]
            and now - c["thumbed_at"] >= DELAY_S]


def tick(reacted=None):
    """Read the channel's reactions for every open card (reacted(ts) -> bool), then return the ready cards."""
    if reacted:
        for cid, c in list(_load().items()):
            if c["state"] in OPEN and c.get("ts"):
                _record(cid, up=reacted(c["ts"]), via="channel")
    return [dict(_load()[cid], card=cid) for cid in ready()]


def _past_delay(c):
    return bool(c.get("thumbed_at")) and time.time() - c["thumbed_at"] >= DELAY_S


def verify(cid, to, cc, subject, body):
    c = _load().get(cid)
    if not c:
        return "no such card"
    if c["state"] != "clock" or not _past_delay(c):
        return "not signed off, or the 2 minutes aren't up"
    if fingerprint(to, cc, subject, body) != c["fp"]:
        return "the draft no longer matches the card the human approved: post the new version instead"
    s = _load()
    s[cid]["verified_fp"] = c["fp"]
    _save(s)
    return "ok"


def lock(cid):
    s = _load()
    c = s.get(cid)
    if not c or c["state"] != "clock" or not _past_delay(c) or c.get("verified_fp") != c["fp"]:
        return False
    c["state"] = "locked"
    _save(s)
    return True


def signed_off(draft_id):
    """For guard.py: True when this draft belongs to a card you've signed off (so edits to it are blocked)."""
    return any(c.get("draft_id") == draft_id and c["state"] in SIGNED for c in _load().values())


def _evidence_ok(cid, c, channel_ok=None):
    if c.get("via") == "terminal":
        return _signature_ok(cid, c)
    if c.get("via") == "channel" and c.get("ts"):
        if channel_ok is None:
            if not common.load_config().get("slack_channel"):
                return False
            import slack
            channel_ok = slack.approved_by_owner
        return bool(channel_ok(c["ts"]))
    return False


def send_allowed(draft_id, channel_ok=None):
    """For guard.py: True once, for a locked card past its 2 minutes whose sign-off evidence checks out now (your
    reaction still on the card, or a terminal signature that checks out against your public key) and whose draft was verified before the lock. It marks
    the card as sending, so a second attempt with the same draft is refused until `done` records what happened."""
    s = _load()
    for cid, c in s.items():
        if (c.get("draft_id") == draft_id and c["state"] == "locked" and _past_delay(c)
                and c.get("verified_fp") == c["fp"] and _evidence_ok(cid, c, channel_ok)):
            c["state"] = "sending"
            _save(s)
            return True
    return False


def done(cid, failed=None):
    s = _load()
    c = s.get(cid)
    if not c or c["state"] not in ("locked", "sending"):
        return False
    c["state"] = "failed" if failed else "sent"
    c["note"] = failed or ""
    _save(s)
    return True


def test():
    import tempfile
    global STATE, _test_keys
    STATE = os.path.join(tempfile.mkdtemp(), "a.json")
    common.INBOX = tempfile.mkdtemp()
    checks = []
    # 1. an intern can't approve: no terminal, or inside an AI tool
    _test_keys = None
    cid = card("ella", "d1", "a@b.com", "Hello", "Body text")
    with open(os.path.join(common.INBOX, common.today(), "cards.md"), encoding="utf-8") as f:
        on_file = f.read()
    checks.append(("card on file, with no code or approve hint", "Body text" in on_file and "code" not in on_file
                   and "approve" not in on_file and _load()[cid]["fp"][:4] not in on_file))
    os.environ["TEAM_AGENT"] = "ella"
    checks.append(("approve refused under an agent", approve(cid, answer=lambda code: code).startswith("refused")))
    os.environ.pop("TEAM_AGENT")
    import io
    saved = {k: os.environ.pop(k) for k in AGENT_MARKERS if k in os.environ}
    real_stdin, sys.stdin = sys.stdin, io.StringIO("")    # piped input: not a terminal
    checks.append(("approve refused without a terminal", approve(cid, answer=lambda code: code).startswith("refused")))
    sys.stdin = real_stdin
    os.environ.update(saved)
    # 2. a forged record (written by hand, no evidence) never sends
    _record(cid, True, at=time.time() - DELAY_S - 1, via="terminal")   # no key: empty signature
    verify(cid, "a@b.com", "", "Hello", "Body text")
    checks.append(("forged terminal sign-off: lock ok", lock(cid)))
    checks.append(("forged terminal sign-off never sends", not send_allowed("d1", channel_ok=lambda ts: True)))
    # 3. the human's own sign-off, with the key
    _test_keys = test_keys()
    c2 = card("ella", "d2", "a@b.com", "Hi", "Real body")
    shown = []
    checks.append(("wrong code refused", approve(c2, answer=lambda code: shown.append(code) or "zzzz").startswith("refused")))
    checks.append(("a fresh code each time, never stored", len(shown) == 1 and shown[0] not in json.dumps(_load())))
    checks.append(("right code ok", approve(c2, answer=lambda code: code, at=time.time() - 10) == "ok"))
    checks.append(("not ready inside 2 minutes", ready() == [] or c2 not in ready()))
    s = _load()
    s[c2]["thumbed_at"] = time.time() - DELAY_S - 1
    s[c2]["sig"] = _sign(_test_keys[0], _message(c2, s[c2]))   # the human's sign-off, backdated for the test
    _save(s)
    checks.append(("ready after 2 minutes", c2 in ready()))
    checks.append(("lock needs verify", not lock(c2)))
    checks.append(("verify catches a changed draft", verify(c2, "a@b.com", "", "Hi", "Changed") != "ok"))
    checks.append(("verify ok", verify(c2, "a@b.com", "", "Hi", "Real body") == "ok"))
    checks.append(("signed off", signed_off("d2")))
    checks.append(("lock after verify", lock(c2) and not lock(c2)))
    tampered = _load()
    tampered[c2]["thumbed_at"] -= 1        # editing the record breaks the signature
    _save(tampered)
    checks.append(("tampered record never sends", not send_allowed("d2")))
    tampered[c2]["thumbed_at"] += 1
    other_key = test_keys()[0]                # signed with any key but the human's: refused
    tampered[c2]["sig"] = _sign(other_key, _message(c2, tampered[c2]))
    _save(tampered)
    checks.append(("a signature from another key never sends", not send_allowed("d2")))
    tampered[c2]["sig"] = _sign(_test_keys[0], _message(c2, tampered[c2]))
    _save(tampered)
    checks.append(("sends once", send_allowed("d2") and not send_allowed("d2")))
    checks.append(("done", done(c2) and _load()[c2]["state"] == "sent"))
    # 4. withdrawn inside the 2 minutes: nothing
    c3 = card("ella", "d3", "a@b.com", "Hi", "x")
    _record(c3, True, at=time.time() - DELAY_S - 1, via="channel")
    _record(c3, False)
    checks.append(("withdrawn", c3 not in ready()))
    # 5. a channel: the reaction is re-checked at send time
    c4 = card("chris", "d4", "x@y.com", "S", "B", poster=lambda text: "300.1")
    checks.append(("posted", _load()[c4]["ts"] == "300.1"))
    tick(reacted=lambda ts: ts == "300.1")
    s = _load()
    s[c4]["thumbed_at"] = time.time() - DELAY_S - 1
    _save(s)
    verify(c4, "x@y.com", "", "S", "B")
    lock(c4)
    checks.append(("reaction gone at send time: refused", not send_allowed("d4", channel_ok=lambda ts: False)))
    checks.append(("reaction still there: sends", send_allowed("d4", channel_ok=lambda ts: True)))
    # 6. a new version resets the sign-off
    c5 = card("chris", "d5", "x@y.com", "S", "B", poster=lambda text: "301.1")
    tick(reacted=lambda ts: True)
    card("chris", "d5", "x@y.com", "S", "B2", card_id=c5, poster=lambda text: "302.1")
    checks.append(("new version resets", _load()[c5]["state"] == "waiting" and _load()[c5]["version"] == 2))
    _test_keys = None
    # off macOS: the key file is encrypted, signs only with your passphrase, and a wrong one signs nothing
    global KEY_DIR, KEY_FILE, PUB_FILE, _on_keychain
    saved_paths, saved_keychain = (KEY_DIR, KEY_FILE, PUB_FILE), _on_keychain
    KEY_DIR = tempfile.mkdtemp()
    KEY_FILE, PUB_FILE = os.path.join(KEY_DIR, "signoff.key"), os.path.join(KEY_DIR, "signoff.pub")
    _on_keychain = lambda: False  # noqa: E731
    priv = _private_key(create=True, passphrase="correct horse battery")
    with open(KEY_FILE, "rb") as f:
        on_disk = f.read()
    c6 = card("ella", "d6", "a@b.com", "S6", "B6")
    c = _load()[c6]
    c["thumbed_at"] = time.time()
    c["sig"] = _sign(priv, _message(c6, c), "correct horse battery")
    checks.append(("off macOS the key file is encrypted and private", b"ENCRYPTED PRIVATE KEY" in on_disk
                   and oct(os.stat(KEY_FILE).st_mode & 0o777) == "0o600" and _private_key() == on_disk))
    checks.append(("it signs with the passphrase", _signature_ok(c6, c)))
    checks.append(("a wrong or missing passphrase signs nothing", _sign(priv, b"m", "wrong guess") == ""
                   and _sign(priv, b"m") == "" and _private_key(create=True) == on_disk))
    (KEY_DIR, KEY_FILE, PUB_FILE), _on_keychain = saved_paths, saved_keychain
    bad = [n for n, ok in checks if not ok]
    for n in bad:
        print("FAIL", n)
    print("approvals: ok" if not bad else "approvals: FAIL")
    sys.exit(0 if not bad else 1)


def main(argv):
    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

    def body():
        with open(opt("--body-file"), encoding="utf-8") as f:
            return f.read()

    cmd, dry = (argv[1] if len(argv) > 1 else ""), "--dry" in argv
    channel = bool(common.load_config().get("slack_channel"))
    if cmd == "card" and opt("--as") and opt("--draft-id") and opt("--to") and opt("--subject") and opt("--body-file"):
        poster = None
        if channel:
            import slack
            poster = lambda text: slack.post(text, dry=dry)  # noqa: E731
        print(card(opt("--as"), opt("--draft-id"), opt("--to"), opt("--subject"), body(), opt("--cc", ""), opt("--card"), poster))
    elif cmd == "approve" and opt("--card"):
        print(approve(opt("--card"), up="--off" not in argv))
    elif cmd == "tick":
        reacted = None
        if channel:
            import slack
            reacted = (lambda ts: False) if dry else slack.approved_by_owner
        for r in tick(reacted):
            print(json.dumps({k: r[k] for k in ("card", "draft_id", "to", "cc", "subject", "agent")}))
    elif cmd == "verify" and opt("--card"):
        print(verify(opt("--card"), opt("--to", ""), opt("--cc", ""), opt("--subject", ""), body()))
    elif cmd == "lock" and opt("--card"):
        print("locked" if lock(opt("--card")) else "can't lock: not signed off, or the 2 minutes aren't up")
    elif cmd == "done" and opt("--card"):
        print("recorded" if done(opt("--card"), opt("--failed")) else "no locked card with that id")
    elif cmd == "list":
        for cid, c in _load().items():
            print(f"{cid}  {c['state']:8}  v{c['version']}  {c['agent']:8}  {c['to']}  {c['subject']}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        test()
    sys.exit(main(sys.argv))
