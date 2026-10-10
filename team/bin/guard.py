#!/usr/bin/env python3
"""The guardrail. Runs as a PreToolUse hook for every intern: `guard.py <agent>`.

Claude Code calls this before each tool call, with the tool name and its input on stdin. Exit 0 lets the call
through; exit 2 blocks it and the reason is shown to the agent (so it can draft or ask instead). Rules, in order:

  1. Nobody deletes, live or scheduled: no trash or delete tools, and no rm, rmdir, unlink, shred, find -delete,
     find -exec rm, git rm, git clean, or Python's shutil.rmtree, os.remove and os.unlink. Words that merely contain
     "rm" (perform, firmware) are fine.
  2. Only the orchestrator sends email. In a live session he sends after your own message armed it (send_ok.py), or
     when the draft is an approved, locked card (approvals.py). In a scheduled run he sends only an approved,
     locked card, by its draft id alone, once the 2-minute undo has passed. Everyone else drafts.
  3. No secrets in commands: anything that reads a keychain, prints an env file or pipes a token is blocked.
  4. Scheduled runs (the env var TEAM_RUN=1, set by tick.py) are stricter: no sends except an approved card, no
     calendar invites, no posting as you, no git push, and no sending data to an API (curl -X POST, -d, --data*,
     -F, --form, --json, -T, wget --post-data, requests.post). They draft and suggest; you decide in the morning.
  5. Raw email APIs in shell commands are blocked for everyone: email leaves only through the tool the
     approvals flow checks.
  6. Nobody touches a payments endpoint. The finance intern reads bank statements; no intern can pay, mandate or pay out.
  7. Nobody signs off on your behalf: `approvals.py approve` and any write to the approval or send state files are
     blocked from every intern, so a sign-off only comes from your reaction or your own terminal. Bash commands are
     read with quotes, backslashes and joining plus signs taken out first (sec''urity, 'appro'+'vals'), and anything
     that fakes a terminal (script, expect, unbuffer, socat, pty), strips the AI-tool markers (env -u, env -i,
     unset), loads code by a built-up name (importlib, __import__) or globs for the sign-off files is blocked.
     Interns can't change team/bin/ or their own .claude/settings*.json either: not with the edit tools, not with a
     shell redirect, sed, cp or mv, and not with code that writes (open for writing, write_text, os.rename, shutil
     copy or move, chmod). install.py also makes those files read-only at the OS level; `install.py --unlock` is for
     you, in your own terminal, and blocked for every intern.

  8. A draft you've signed off can't be edited (update, edit, save or replace, with the id passed as draftId,
     draft_id, draftID or {"draft": {"id": ...}}): the intern posts a new version
     of the card instead. Rule 7 also covers reactions: no intern can add or remove one in any channel, so none can
     put your thumbs up on its own card. And approvals.py checks the evidence for every sign-off at send time, so a
     hand-written approval record gets nothing sent.
  9. What an intern writes is checked before it lands, so a file can't carry what a command couldn't. A script
     (.py, .sh and other code files, anything starting #!, or a file with no extension) gets the command checks
     above, line by line. Notes, drafts and data get only the code-shaped ones (importing approvals, stripping the
     markers, rmtree and remove, writing to the protected files), so ordinary words never trip them. Running a note
     or data file as code (python3 notes.md, source notes.txt, exec(open(...))) is blocked.

Known limit: this is pattern matching. It stops the routes it knows, and the disguises above, but deliberately
obfuscated code (a name built at run time, an encoded string) can still get past it. That's why the protected files
are read-only at the OS level and terminal sign-offs are signed; for hard isolation, run the interns under a
separate OS user or in a container (AGENTS.md lists every limit).

Tools are matched by what they do, not what they're called: the action part of `mcp__<server>__<action>` is
normalised (lower case, separators removed), so `sendMail`, `send-email`, `send_email` and `SendEmail` all read the
same, on any server ("gmail", "gmail-work", "claude_ai_Gmail", "outlook", "my.mail.box"), and dispatch, deliver,
respond and create-a-message count as sends. Chat tools (Slack, Teams, Discord, Telegram, WhatsApp) post as you, so
only the orchestrator can use them, live and armed like an email; the cards and report go out as the bot through
slack.py. If you add a tool these words miss, add the word to the lists below and a test.

Usage:  guard.py <agent>      hook mode (reads JSON from stdin)
        guard.py --test       self-test"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

SEND_WORDS = ("send", "reply", "forward", "dispatch", "deliver", "respond")
SEND_OBJECTS = ("email", "mail", "message", "draft", "all")
MAIL_OBJECTS = ("email", "mail", "message")
CREATE_WORDS = ("create", "compose", "new", "post", "submit")
READ_WORDS = ("get", "list", "read", "fetch", "search", "count")
EDIT_WORDS = ("update", "edit", "modify", "replace", "patch", "change", "save", "put", "set", "write", "upsert")
CHAT_SERVER = re.compile(r"(slack|teams|discord|telegram|whatsapp|chat)", re.I)
CHAT_SEND = ("send", "post", "reply", "publish", "schedule", "update", "share", "write")
NOT_MAIL = re.compile(r"(calendar|event)", re.I)
DELETE_TOOLS = re.compile(r"(delete_|trash_|batch_delete|remove_)", re.I)
INVITE_FIELDS = ("attendees", "attendeeEmails", "addedAttendees")
POST_AS_YOU = re.compile(r"^mcp__.*(slack|linkedin|twitter|x)__.*(send|post|publish|schedule)", re.I)
# Where a shell command starts: the start, after ; & | ( ` { [ , or $(, or after then/do, past sudo, env or xargs.
_AT_COMMAND = (r"(?:^|[;&|(`{\[,]|\$\(|\b(?:then|do)\b)\s*(?:\w+=\S*\s+)*"
               r"(?:(?:sudo|exec|nohup|command|xargs|time|env)\s+(?:-\S+\s+|\w+=\S*\s+)*)*(?:/\S*/)?")
# Any delete: rm, rmdir, unlink or shred as a command (not "rm" inside a word such as "perform"), rm with flags
# anywhere (bash -c "rm -r x"), find -delete or -exec rm, git rm or clean, and Python's rmtree, remove and unlink.
BASH_DELETE = re.compile(_AT_COMMAND + r"(rm|rmdir|unlink|shred|srm)\b"
                         r"|\b(rm|rmdir)\s+-{1,2}[a-z]|-(c|exec|execdir|ok)\s+(\S*/)?(rm|rmdir|unlink|shred)\b"
                         r"|\bfind\b[^;&|]*\s-delete\b|\bgit\s+(rm|clean)\b"
                         r"|\bshutil\s*\.\s*rmtree|\bos\s*\.\s*(remove|unlink|rmdir|removedirs)\s*\(|\.(unlink|rmdir)\s*\("
                         r"|\bgit\s+push\s+.*--force|\bdrop\s+table\b", re.I)
BASH_SECRETS = re.compile(r"(\bsecurity\s+(find|add|delete|dump|export|unlock|set|import)-?\w*|cat\s+\S*\.env\b|printenv|\$\{?\w*(TOKEN|SECRET|KEY)\w*\}?\s*$)", re.I)
BASH_MAIL_RAW = re.compile(r"(gmail\.googleapis\.com|/messages/send|/drafts/send|smtplib|smtp\.|sendmail\b)", re.I)
BASH_PAYMENTS = re.compile(r"(/payments\b|/mandates\b|/payouts\b|single-immediate-payment|payment_initiation)", re.I)
PAY_TOOLS = re.compile(r"(create_payment|initiate_payment|make_payment|send_money|transfer_funds|payout)", re.I)
SELF_APPROVE = re.compile(r"(approvals\.py\s+approve\b|\.approvals\.json|\.send-ok\.json|"
                          r"(import|from)\s+approvals\b|['\"]approvals['\"]|_record\s*\(|agent-interns|"
                          r"\.config/agent-interns|signoff\.(key|pub)|reactions\.add|/reactions\b|"
                          r"importlib|__import__|\bimp\.load|runpy|"                       # loading code by a built-up name
                          r"\bapprove\s+--card\b|team/bin/\S*[*?\[]|appro\S*[*?\[]|\bsign\S*[*?\[]|"   # globs aimed
                          r"(~|\$\{?HOME\}?|/Users/[^/\s]+|/home/[^/\s]+)/\.[\w.-]*[*?\[]|\.config/\S*[*?\[])", re.I)
_MARKERS = r"(CLAUDECODE|CLAUDE_CODE_ENTRYPOINT|CODEX_SANDBOX|CODEX_MANAGED_BY_NPM|GEMINI_CLI|CURSOR_TRACE_ID|TEAM_AGENT|TEAM_RUN)"
FAKE_TERMINAL = re.compile(_AT_COMMAND + r"(script|expect|unbuffer|socat|tmux|screen)\b|\bunbuffer\b|\bsocat\b|"
                           r"\bpty\b|openpty|forkpty|"
                           r"\benv\s+(-\S+\s+|\w+=\S*\s+)*(-[a-z]*[iu]\b|-(\s|$)|--unset|--ignore-environment)|"
                           r"\bunset\s+(-v\s+)?" + _MARKERS + r"|\b" + _MARKERS + r"\b\]?\s*=\s*($|[\s;&|)])|"
                           r"\bos\.(unsetenv|putenv)|\bos\.environ\.(pop|clear)|\bdel\s+os\.environ|\benv\s*=\s*\{",
                           re.I)
# Interns never edit the guard, the sign-off code or their own settings.
PROTECTED = re.compile(r"((^|/)team/bin/|(^|/)\.claude/settings[\w.-]*\.json$)", re.I)
BASH_PROTECTED = re.compile(r"(>>?|\btee\b|\bsed\s+-i\S*|\bmv\b|\bcp\b|\bln\b|\bchmod\b|\btruncate\b|\bperl\s+-\S*i)"
                            r"[^;&|]*?(team/bin/|\.claude/settings)|\binstall\.py\b[^;&|]*--unlock", re.I)
# Code that writes a file (open for writing, pathlib, rename, copy, move, chmod, links), anywhere in the same command
# or file as a protected path. install.py also makes those files read-only, so this is the second layer.
WRITE_CALL = re.compile(r"\bopen\s*\([^)]*,\s*(mode\s*=\s*)?[rwab]?[wax+]|\bwrite_(text|bytes)\s*\(|"
                        r"\bos\s*\.\s*(rename|replace|chmod|lchmod|chflags|symlink|link|truncate|open)\s*\(|"
                        r"\bshutil\s*\.\s*(copy\w*|move)\s*\(|\.(rename|replace|symlink_to|hardlink_to|chmod|touch)\s*\(",
                        re.I)
PROTECTED_WORDS = re.compile(r"team/bin|\.claude/settings", re.I)
# Running a note or data file as code (python3 notes.md, source notes.txt, exec(open(...))): a way round the checks
# on what interns write, which are lighter for notes and drafts than for code.
RUN_NON_CODE = re.compile(_AT_COMMAND + r"(python[\d.]*|bash|sh|zsh|fish|node|deno|ruby|perl|php|osascript|source|\.)\s+"
                          r"(-\S+\s+)*[\w.~/@+][\w.~/@+-]*\.(md|markdown|txt|json|csv|log|html?|ya?ml|toml|ini|cfg|xml)(?=$|[\s;&|)])|"
                          r"\b(exec|compile|eval)\s*\(\s*(open|pathlib|Path)\b|"
                          r"\b(python[\d.]*|bash|sh|zsh|node|ruby|perl)\s*<\s*[\w.~/@+][\w.~/@+-]*\.(md|markdown|txt|json|csv|log)\b", re.I)
# Files that run as code: checked like a shell command, line by line. Anything else (notes, drafts, data) is checked
# only for code-shaped text, so ordinary words ("approved?", "screen the calls") never trip it.
CODE_FILE = re.compile(r"(\.(py|pyw|sh|bash|zsh|fish|command|js|mjs|cjs|ts|rb|pl|php|lua|applescript|scpt|ps1|bat|cmd)"
                       r"|(^|/)[^./]+)$", re.I)
SELF_CODE = re.compile(r"(import|from)\s+approvals\b|\b_record\s*\(|\bimportlib\b|__import__|\bimp\.load|\brunpy\b", re.I)
TERMINAL_CODE = re.compile(r"\bos\s*\.\s*(unsetenv|putenv)|\bos\s*\.\s*environ\s*\.\s*(pop|clear)|\bdel\s+os\s*\.\s*environ|"
                           r"\b(openpty|forkpty)\b|\bpty\s*\.\s*spawn", re.I)
DELETE_CODE = re.compile(r"\bshutil\s*\.\s*rmtree|\bos\s*\.\s*(remove|unlink|rmdir|removedirs)\s*\(", re.I)
BASH_SCHEDULED = re.compile(r"(\bgit\s+push\b|\bosascript\b|\bcurl\b.*-X\s*(POST|PUT|PATCH|DELETE)|"
                            r"\bcurl\b.*\s(?-i:-d|-F|-T)|\bcurl\b.*\s--(data\S*|form\S*|json|upload-file)\b|"
                            r"\bwget\b.*\s--(post|body|method)\S*|\bhttps?\s+(POST|PUT|PATCH|DELETE)\b|"
                            r"\brequests\s*\.\s*(post|put|patch|delete)\s*\(|\burlopen\s*\([^)]*data\s*=)", re.I)

ONLY_ORCHESTRATOR = ("Only the orchestrator sends email. Draft it and hand it over: your human approves the draft "
                     "card, or tells the orchestrator to send.")
NEEDS_ARMING = ("The orchestrator sends only after the human's own message said to send this email. Ask first; don't send.")


def normalise_command(cmd):
    """A shell command with the simple disguises taken off: quotes, backslashes and string-joining plus signs, so
    sec''urity, 'appro'+'vals' and appro\\vals all read as the word they spell. Deliberate obfuscation can still beat
    a pattern match; that's a known limit (AGENTS.md)."""
    t = re.sub(r"[\\'\"]", "", cmd or "")
    t = re.sub(r"(?<=\w)\s*\+\s*(?=\w)", "", t)
    return t


def _norm_key(k):
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def draft_ids(inp, draftish=True):
    """Every draft id in a tool's input, however it's passed: draftId, draft_id, draftID, or nested {"draft": {"id": …}}."""
    found = []
    if isinstance(inp, dict):
        for k, v in inp.items():
            nk = _norm_key(k)
            if isinstance(v, (dict, list)):
                found += draft_ids(v, draftish="draft" in nk)
            elif v and (nk == "draftid" or (nk == "id" and draftish)):
                found.append(str(v))
    elif isinstance(inp, list):
        for v in inp:
            found += draft_ids(v, draftish)
    return found


def split_tool(tool):
    """(server, normalised action) for an MCP tool, else None: 'mcp__gmail-work__sendMail' -> ('gmail-work', 'sendmail')."""
    if not tool.startswith("mcp__"):
        return None
    parts = tool.split("__")
    if len(parts) < 3:
        return None
    return "__".join(parts[1:-1]), re.sub(r"[^a-z0-9]", "", parts[-1].lower())


def _sends(action):
    if any(action.startswith(w) or action.endswith(w) or any(w + o in action for o in SEND_OBJECTS)
           for w in SEND_WORDS):
        return True
    # "emails_create", "create_message", "new_mail": creating a message (not a draft) is a send on most mail APIs
    return ("draft" not in action and any(o in action for o in MAIL_OBJECTS)
            and any(c in action for c in CREATE_WORDS))


def is_email_send(tool):
    """True for a tool that sends, replies or forwards email, whatever its server or action is called."""
    st = split_tool(tool)
    if not st:
        return False
    server, action = st
    if not _sends(action) or any(action.startswith(r) for r in READ_WORDS):
        return False
    if NOT_MAIL.search(server) or NOT_MAIL.search(action):
        return False   # answering a calendar invite isn't an email
    return not (CHAT_SERVER.search(server) or CHAT_SERVER.search(action))


def is_chat_send(tool):
    """Posting or sending in Slack, Teams, Discord, Telegram or WhatsApp through a connector: that posts as you."""
    st = split_tool(tool)
    if not st:
        return False
    server, action = st
    if not (CHAT_SERVER.search(server) or CHAT_SERVER.search(action)):
        return False
    if any(action.startswith(r) for r in READ_WORDS) or "react" in action:
        return False   # reads are fine; reactions have their own rule
    return any(w in action for w in CHAT_SEND)


def is_reaction(tool):
    """Any tool that adds or removes a reaction, on any server: the one way an intern could fake your thumbs up."""
    st = split_tool(tool)
    return bool(st) and "react" in st[1] and not re.search("(%s)[a-z]*react" % "|".join(READ_WORDS), st[1])


def is_draft_edit(tool):
    st = split_tool(tool)
    return bool(st) and "draft" in st[1] and any(w in st[1] for w in EDIT_WORDS) and not st[1].startswith("send")


def approved_draft(inp):
    """The draft id if this send is an approved, locked card past its 2 minutes (approvals.py), else None."""
    import approvals
    ids = draft_ids(inp)
    extra = [k for k, v in inp.items() if v and _norm_key(k) not in ("draftid", "id", "draft")]
    if len(set(ids)) != 1 or extra:
        return None
    return ids[0] if approvals.send_allowed(ids[0]) else None


def written_text(tool, inp):
    """What a Write, Edit, MultiEdit or NotebookEdit call puts in the file: content, new_string, every edit, new_source."""
    if tool not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return ""
    parts = [inp.get(k) for k in ("content", "new_string", "new_source")]
    parts += [e.get("new_string") for e in inp.get("edits") or [] if isinstance(e, dict)]
    return "\n".join(p for p in parts if isinstance(p, str))


def protected_write(text):
    return bool(WRITE_CALL.search(text) and PROTECTED_WORDS.search(text))


def content_reason(path, text):
    """Why a file an intern writes would get round the rules once it's run, or None. A script is checked the way a
    command is, line by line; notes, drafts and data only for code-shaped text."""
    if not text:
        return None
    norm = normalise_command(text)
    code = bool(CODE_FILE.search(path)) or text.lstrip().startswith("#!")
    lines = [normalise_command(line) for line in text.splitlines()] if code else []
    if SELF_CODE.search(norm) or (code and (SELF_APPROVE.search(norm) or SELF_APPROVE.search(text))):
        return "self"
    if protected_write(norm):
        return "protected"
    if TERMINAL_CODE.search(norm) or any(FAKE_TERMINAL.search(line) for line in lines):
        return "terminal"
    if DELETE_CODE.search(norm) or any(BASH_DELETE.search(line) for line in lines):
        return "delete"
    return None


SELF_APPROVE_WHY = "Only your human signs off: from their reaction on the card, or their own terminal. Ask them."
PROTECTED_WHY = "Interns don't change the guard, the sign-off scripts or their own settings. Ask your human."
TERMINAL_WHY = ("That fakes a terminal or hides that an AI tool is running. Sign-offs come from your human's own "
                "terminal or their reaction, never an intern.")
DELETE_WHY = "Interns never delete. Suggest it to your human instead."


def check(agent, tool, inp, scheduled=False):
    """Return a reason to block, or None."""
    raw = inp.get("command", "") if tool == "Bash" else ""
    cmd = normalise_command(raw) if raw else ""
    path = str(inp.get("file_path") or inp.get("path") or inp.get("notebook_path") or "") \
        if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit") else ""
    written = content_reason(path, written_text(tool, inp))
    if written:
        return {"self": SELF_APPROVE_WHY, "protected": PROTECTED_WHY, "terminal": TERMINAL_WHY,
                "delete": DELETE_WHY}[written]
    if (cmd and (SELF_APPROVE.search(cmd) or SELF_APPROVE.search(raw))) or (path and SELF_APPROVE.search(path)) \
            or is_reaction(tool):
        return SELF_APPROVE_WHY
    if (path and PROTECTED.search(path)) or (cmd and (BASH_PROTECTED.search(cmd) or protected_write(cmd))):
        return PROTECTED_WHY
    if cmd and FAKE_TERMINAL.search(cmd):
        return TERMINAL_WHY
    if cmd and RUN_NON_CODE.search(cmd):
        return ("Notes, drafts and data files aren't run as code. Put a script in a .py or .sh file, where the guard "
                "can read it first.")
    if is_draft_edit(tool):
        import approvals
        if any(approvals.signed_off(d) for d in draft_ids(inp)):
            return "Your human signed this draft off as it is. To change it, post a new version of the card."
    if DELETE_TOOLS.search(tool) or (cmd and BASH_DELETE.search(cmd)):
        return DELETE_WHY
    if cmd and BASH_SECRETS.search(cmd):
        return "That command would expose a secret. Keys live in the keychain or env, and never in a session."
    if cmd and BASH_MAIL_RAW.search(cmd):
        return "Email leaves only through the approved send tool, never a hand-rolled API call."
    if PAY_TOOLS.search(tool) or (cmd and BASH_PAYMENTS.search(cmd)):
        return "Interns never move money. Arthur reads bank statements and drafts; payments are yours to make."
    if is_email_send(tool):
        if agent != common.orchestrator():
            return ONLY_ORCHESTRATOR
        if approved_draft(inp):
            return None
        if scheduled:
            return ("Scheduled runs send only an approved, locked card, by its draft id alone, after the 2-minute "
                    "undo. Draft it; the morning report will show it.")
        import send_ok
        return None if send_ok.consume() else NEEDS_ARMING
    if is_chat_send(tool):
        if agent != common.orchestrator():
            return ("Connectors post in your human's name, so only the orchestrator can, and only when they've said "
                    "to. Draft it: cards and the report go out as the bot through team/bin/slack.py.")
        if scheduled:
            return "Scheduled runs don't post or message as your human. Draft it for the morning."
        import send_ok
        return None if send_ok.consume() else NEEDS_ARMING
    if scheduled:
        if any(inp.get(k) for k in INVITE_FIELDS):
            return "Scheduled runs don't invite people to meetings. Block the time, and ask in the report."
        if POST_AS_YOU.search(tool):
            return "Scheduled runs don't post or message as your human. Draft it for the morning."
        if cmd and BASH_SCHEDULED.search(cmd):
            return "Scheduled runs don't push, POST to APIs or run scripts on the desktop. Suggest it instead."
    return None


def main():
    agent = sys.argv[1] if len(sys.argv) > 1 else "?"
    data = json.load(sys.stdin)
    tool, inp = data.get("tool_name", ""), data.get("tool_input") or {}
    why = check(agent, tool, inp, scheduled=os.environ.get("TEAM_RUN") == "1")
    if not why:
        sys.exit(0)
    common.log_line(os.path.join(common.LOGS, "guard.log"), f"{agent} {tool} blocked: {why}")
    print(f"Blocked by the team guard: {why}", file=sys.stderr)
    sys.exit(2)


def test():
    import tempfile
    os.environ["SEND_OK_FILE"] = os.path.join(tempfile.mkdtemp(), "send-ok.json")
    orch = common.orchestrator()
    cases = [  # (agent, tool, input, scheduled, should_block)
        ("arthur", "Bash", {"command": "curl https://api.truelayer.com/v3/payments"}, False, True),
        ("arthur", "mcp__bank__create_payment", {}, False, True),
        ("arthur", "Bash", {"command": "python3 tools/truelayer.py pull --from 2026-04-06"}, True, False),
        ("ella", "mcp__gmail__send_message", {"to": ["a@b.com"]}, False, True),
        (orch, "mcp__gmail__send_message", {"to": ["a@b.com"]}, False, True),   # not armed
        (orch, "mcp__gmail__send_message", {"to": ["a@b.com"]}, True, True),    # scheduled
        ("ella", "mcp__gmail__create_draft", {"to": ["a@b.com"]}, True, False),
        ("ella", "mcp__gmail__trash_thread", {"id": "x"}, False, True),
        ("ella", "Bash", {"command": "rm -rf build"}, False, True),
        ("ella", "Bash", {"command": "ls -la"}, False, False),
        ("ella", "Bash", {"command": "security find-generic-password -s x -w"}, False, True),
        ("ella", "Bash", {"command": "python3 -c 'import smtplib'"}, False, True),
        ("ella", "Bash", {"command": "git push"}, True, True),
        ("ella", "Bash", {"command": "git push"}, False, False),
        ("chris", "mcp__slack__slack_send_message", {"text": "hi"}, True, True),
        ("chris", "mcp__slack__slack_send_message", {"text": "hi"}, False, True),      # posts as you: never
        (orch, "mcp__calendar__create_event", {"attendees": ["x@y.com"]}, True, True),
        (orch, "mcp__calendar__create_event", {"summary": "Focus"}, True, False),
        # sends are matched by action, whatever the server is called
        ("ella", "mcp__gmail-work__send_email", {"to": ["a@b.com"]}, False, True),
        (orch, "mcp__gmail-work__send_email", {"to": ["a@b.com"]}, False, True),     # not armed
        (orch, "mcp__gmail-work__send_email", {"to": ["a@b.com"]}, True, True),
        ("chris", "mcp__claude_ai_Gmail__send_message", {}, False, True),
        ("chris", "mcp__my.mail.box__reply_all", {}, False, True),
        ("chris", "mcp__outlook_365__forward", {}, False, True),
        ("chris", "mcp__google-workspace__send_draft", {"draftId": "d"}, False, True),
        ("chris", "mcp__fastmail__email_send", {}, False, True),
        (orch, "mcp__gmail-work__send_email", {"draftId": "unknown"}, True, True),  # no approved card for it
        ("chris", "mcp__gmail__create_draft", {}, False, False),
        ("chris", "mcp__team-slack__slack_send_message", {"text": "hi"}, False, True),
        ("ella", "mcp__claude_ai_Slack__slack_schedule_message", {"text": "hi"}, False, True),
        ("arthur", "mcp__teams__postMessage", {}, False, True),
        ("chris", "mcp__discord__send", {}, False, True),
        (orch, "mcp__slack__slack_send_message", {"text": "hi"}, False, True),       # not armed
        (orch, "mcp__slack__slack_send_message", {"text": "hi"}, True, True),        # scheduled
        ("chris", "mcp__slack__slack_read_channel", {}, False, False),
        ("chris", "mcp__slack__slack_search_public", {}, False, False),
        # round 6: other send names, and calendar answers aren't email
        ("chris", "mcp__mail__dispatch", {}, False, True),
        ("chris", "mcp__outlook__emails_create", {}, False, True),
        ("ella", "mcp__helpdesk__respond_to_email", {}, False, True),
        ("ella", "mcp__mail__deliver_email", {}, False, True),
        ("ella", "mcp__mail__dispatchMessage", {}, False, True),
        ("ella", "mcp__mail__create_message", {}, False, True),
        ("ella", "mcp__mail__drafts_create", {}, False, False),
        ("ella", "mcp__calendar__respond_to_event", {}, False, False),
        # round 6: faked terminals, stripped markers, disguised names, globs
        (orch, "Bash", {"command": "env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT script -q /dev/null python3 "
                                   "../../team/bin/appro*.py approve --card C"}, False, True),
        (orch, "Bash", {"command": "script -q /dev/null python3 x.py"}, False, True),
        (orch, "Bash", {"command": "cd /tmp; expect run.exp"}, False, True),
        (orch, "Bash", {"command": "unbuffer python3 x.py"}, False, True),
        (orch, "Bash", {"command": "socat - EXEC:python3,pty"}, False, True),
        (orch, "Bash", {"command": "python3 -c 'import pty; pty.spawn([\"python3\"])'"}, False, True),
        (orch, "Bash", {"command": "env -i python3 x.py"}, False, True),
        (orch, "Bash", {"command": "CLAUDECODE= python3 x.py"}, False, True),
        (orch, "Bash", {"command": "python3 -c \"import importlib; importlib.import_module('appro'+'vals')\""}, False, True),
        (orch, "Bash", {"command": "sec''urity find-generic-password -s x -w"}, False, True),
        (orch, "Bash", {"command": "s\\ecurity find-generic-password -s x -w"}, False, True),
        ("ella", "Bash", {"command": "cat ~/.config/agent-interns/sign*"}, False, True),
        ("ella", "Bash", {"command": "cat ~/.c*/a*/s*"}, False, True),
        ("ella", "Bash", {"command": "cd ../../team/bin && python3 a*.py approve --card C"}, False, True),
        ("ella", "Write", {"file_path": "../../team/bin/guard.py", "content": "x"}, False, True),
        ("ella", "Edit", {"file_path": "/x/agents/ella/.claude/settings.json", "old_string": "a", "new_string": "b"}, False, True),
        # ordinary work still runs
        ("chris", "Bash", {"command": "git commit -m 'add a script for the expected posts'"}, False, False),
        ("ella", "Bash", {"command": "git push -u origin main"}, False, False),
        ("ella", "Bash", {"command": "ls ~/Documents/*.md"}, False, False),
        ("ella", "Bash", {"command": "python3 tools/sell_sheet.py --draft 'Hi Sam'"}, False, False),
        # nobody approves on the human's behalf
        (orch, "Bash", {"command": "python3 ../../team/bin/approvals.py approve --card c1"}, False, True),
        ("ella", "Bash", {"command": "echo '{}' > ../../team/.approvals.json"}, False, True),
        (orch, "Write", {"file_path": "/x/team/.send-ok.json", "content": "{}"}, False, True),
        ("ella", "Bash", {"command": "python3 ../../team/bin/approvals.py card --as ella --draft-id d"}, False, False),
        (orch, "Bash", {"command": "python3 ../../team/bin/approvals.py tick"}, True, False),
        # camelCase and hyphenated actions, any server (round 5)
        ("ella", "mcp__outlook__sendMail", {"to": ["a@b.com"]}, False, True),
        ("chris", "mcp__x__sendEmail", {}, False, True),
        ("arthur", "mcp__y__send-email", {}, True, True),
        (orch, "mcp__outlook__sendMail", {"to": ["a@b.com"]}, False, True),        # not armed
        ("chris", "mcp__mail__ReplyAll", {}, False, True),
        ("chris", "mcp__mail__getSendStatus", {}, False, False),                   # a read, not a send
        ("chris", "mcp__gmail__list_sent_messages", {}, False, False),
        # reactions: no intern can add or remove one, anywhere, live or scheduled
        (orch, "mcp__claude_ai_Slack__slack_add_reaction", {"name": "+1"}, False, True),
        ("ella", "mcp__teams__addReaction", {}, True, True),
        ("chris", "mcp__discord__react", {}, False, True),
        ("chris", "mcp__slack__slack_get_reactions", {}, False, False),             # reading is fine
        ("ella", "Bash", {"command": "curl -s https://slack.com/api/reactions.add -d name=thumbsup"}, False, True),
        # inline code reaching for the approvals module or the sign-off key
        (orch, "Bash", {"command": "python3 -c \"import approvals; approvals.approve('c1')\""}, False, True),
        (orch, "Bash", {"command": "cd ../../team/bin && python3 -c 'from approvals import _record'"}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"__import__('approvals')\""}, False, True),
        ("ella", "Bash", {"command": "cat ~/.config/agent-interns/signoff.key"}, False, True),
        (orch, "Bash", {"command": "security find-generic-password -s agent-interns-signoff -w"}, False, True),
        # fix 1: code that writes over the guard or the settings, and unlocking them
        ("ella", "Bash", {"command": "python3 -c \"open('../../team/bin/guard.py','w').write('')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import pathlib; pathlib.Path('../../team/bin/guard.py').write_text('')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import os; os.rename('x.py', '../../team/bin/guard.py')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import shutil; shutil.copy('x.json', '.claude/settings.json')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import os; os.chmod('../../team/bin/guard.py', 0o644)\""}, False, True),
        ("ella", "Bash", {"command": "python3 ../../install.py --unlock"}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"open('out/sheet.md','w').write('x')\""}, False, False),
        ("ella", "Bash", {"command": "python3 ../../team/bin/brief.py inputs > out/inputs.md"}, False, False),
        # fix 2: every delete, while words with "rm" inside them still pass
        ("ella", "Bash", {"command": "rm -r old"}, False, True),
        ("ella", "Bash", {"command": "rm file.txt"}, False, True),
        ("ella", "Bash", {"command": "find . -delete"}, False, True),
        ("ella", "Bash", {"command": "find . -name '*.tmp' -exec rm {} \\;"}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import shutil; shutil.rmtree('out')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import os; os.remove('x')\""}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"import os; os.unlink('x')\""}, False, True),
        ("ella", "Bash", {"command": "rmdir old"}, False, True),
        ("ella", "Bash", {"command": "unlink x"}, False, True),
        ("ella", "Bash", {"command": "ls && rm notes.md"}, False, True),
        ("ella", "Bash", {"command": "/bin/rm notes.md"}, False, True),
        ("ella", "Bash", {"command": "bash -c 'rm -r out'"}, False, True),
        ("ella", "Bash", {"command": "xargs rm < list.txt"}, False, True),
        ("ella", "Bash", {"command": "git rm notes.md"}, False, True),
        ("chris", "Bash", {"command": "npm run format"}, False, False),
        ("chris", "Bash", {"command": "python3 tools/hooks.py score --perform"}, False, False),
        ("chris", "Bash", {"command": "grep -rn firmware ."}, False, False),
        ("chris", "Bash", {"command": "git commit -m 'confirm the rm list with Sam'"}, False, False),
        # fix 3: a file written now and run later is checked as it's written
        ("ella", "Write", {"file_path": "tools/x.py", "content": "import approvals\napprovals.approve('c1')\n"}, False, True),
        ("ella", "Write", {"file_path": "tools/x.py", "content": "open('../../team/bin/guard.py', 'w').write('')\n"}, False, True),
        ("ella", "Write", {"file_path": "tools/x.sh", "content": "#!/bin/sh\nrm -r ../chris\n"}, False, True),
        ("ella", "Write", {"file_path": "run", "content": "find . -delete\n"}, False, True),
        ("ella", "Write", {"file_path": "tools/x.py", "content": "import os\nos.environ.pop('CLAUDECODE')\n"}, False, True),
        ("ella", "Write", {"file_path": "tools/x.py", "content": "import subprocess\nsubprocess.run(['script', '-q'])\n"}, False, True),
        ("ella", "Edit", {"file_path": "tools/x.py", "old_string": "a", "new_string": "shutil.rmtree('out')"}, False, True),
        ("ella", "MultiEdit", {"file_path": "tools/x.py", "edits": [{"old_string": "a", "new_string": "from approvals import _record"}]}, False, True),
        ("ella", "NotebookEdit", {"notebook_path": "n.ipynb", "new_source": "import approvals"}, False, True),
        ("ella", "Write", {"file_path": "out/notes.md", "content": "```python\nimport approvals\n```\n"}, False, True),
        ("ella", "Bash", {"command": "python3 out/notes.md"}, False, True),
        ("ella", "Bash", {"command": "python3 -c \"exec(open('out/notes.md').read())\""}, False, True),
        ("ella", "Bash", {"command": "sh < out/notes.txt"}, False, True),
        ("ella", "Write", {"file_path": "memory/MEMORY.md", "content": "Sam approved? Yes, he **signed off** the draft. "
                           "Expect replies by Friday; screen the calls, firm up the rm list, perform a check.\n"}, False, False),
        ("ella", "Write", {"file_path": "tools/count.py", "content": "import csv\nrows = list(csv.reader(open('out/x.csv')))\n"
                           "print(len(rows))\n"}, False, False),
        ("theo", "Write", {"file_path": "out/brief.md", "content": "Run python3 ../../team/bin/brief.py inputs first.\n"}, False, False),
        ("arthur", "Bash", {"command": "python3 tools/categorise.py out/statement.csv"}, False, False),
        ("arthur", "Bash", {"command": "python3 -m json.tool out/ledger.json"}, False, False),
        # fix 4: scheduled runs can't POST by any of curl's data flags
        ("ella", "Bash", {"command": "curl -d 'a=1' https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "curl --data @f.json https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "curl --data-raw x https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "curl -F file=@x.csv https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "curl --json '{}' https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "curl -T x.csv https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "wget --post-data=a=1 https://api.example.com"}, True, True),
        ("ella", "Bash", {"command": "python3 -c \"import requests; requests.post('https://api.example.com')\""}, True, True),
        ("ella", "Bash", {"command": "curl -s https://api.example.com/v1/items"}, True, False),
        ("ella", "Bash", {"command": "curl -D headers.txt https://api.example.com"}, True, False),
        ("ella", "Bash", {"command": "curl -d 'a=1' https://api.example.com"}, False, False),
    ]
    bad = [c for c in cases if (check(*c[:4]) is not None) != c[4]]
    import send_ok
    send_ok.arm("send it")
    armed = check(orch, "mcp__gmail__send_message", {"to": ["a@b.com"]}) is None
    second = check(orch, "mcp__gmail__send_message", {"to": ["a@b.com"]}) is not None  # one send only
    import approvals
    import time
    approvals.STATE = os.path.join(tempfile.mkdtemp(), "a.json")
    approvals.common.INBOX = tempfile.mkdtemp()
    approvals._test_keys = approvals.test_keys()          # the human's keys, for the test only
    cid = approvals.card("ella", "d9", "a@b.com", "Hi", "Body")
    approvals.approve(cid, answer=lambda code: code, at=time.time() - approvals.DELAY_S - 1)
    early = check(orch, "mcp__gmail__send_message", {"draftId": "d9"}, True) is not None   # not verified or locked
    no_lock_without_verify = not approvals.lock(cid)
    edit_blocked = check("ella", "mcp__gmail__update_draft", {"draftId": "d9"}, False) is not None
    edit_other_ok = check("ella", "mcp__gmail__update_draft", {"draftId": "d-other"}, False) is None
    edit_blocked = edit_blocked and all(check("ella", t, i, False) is not None for t, i in (
        ("mcp__gmail__update_draft", {"draftID": "d9"}),
        ("mcp__gmail__update_draft", {"draft": {"id": "d9", "message": {"raw": "x"}}}),
        ("mcp__mail__save_draft", {"draft_id": "d9"}),
        ("mcp__mail__saveDraft", {"draftId": "d9"}),
        ("mcp__outlook__drafts_update", {"id": "d9"})))
    approvals.verify(cid, "a@b.com", "", "Hi", "Body")
    approvals.lock(cid)
    extra = check(orch, "mcp__gmail__send_message", {"draftId": "d9", "to": ["z@z.com"]}, True) is not None
    locked = check(orch, "mcp__gmail__send_message", {"draftId": "d9"}, True) is None
    again = check(orch, "mcp__gmail__send_message", {"draftId": "d9"}, True) is not None  # once only
    other = check("ella", "mcp__gmail__send_message", {"draftId": "d9"}, True) is not None
    # a hand-written "approved" record (no valid signature) never sends
    forged = approvals.card("ella", "d10", "a@b.com", "Hi", "Body")
    approvals._record(forged, True, at=time.time() - approvals.DELAY_S - 1, via="terminal")   # no signature
    approvals.verify(forged, "a@b.com", "", "Hi", "Body")
    approvals.lock(forged)
    forged_blocked = check(orch, "mcp__gmail__send_message", {"draftId": "d10"}, True) is not None
    approvals._test_keys = None
    for c in bad:
        print("FAIL", c)
    flow = (early and no_lock_without_verify and edit_blocked and edit_other_ok and extra and locked and again
            and other and forged_blocked)
    if not flow:
        print("FAIL approved-card flow", early, extra, locked, again, other)
    ok = not bad and armed and second and flow
    print(f"guard: {len(cases) + 2 - len(bad) - (0 if armed else 1) - (0 if second else 1)}/{len(cases) + 2} checks pass")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    test() if "--test" in sys.argv else main()
