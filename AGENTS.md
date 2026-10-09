# Setting up the interns with an AI coding tool

This file is for AI coding tools (Claude Code, Codex, Gemini CLI and others). **If your working folder is inside
`agents/<name>/`, ignore this file: you are that intern, and the AGENTS.md in that folder is your brief.**

When the person asks you to set up their interns (in whatever words), do these four steps in order.

## 1. Read the code first, and tell them what it touches

Read `install.py`, every script in `team/bin/` and `agents/*/tools/`, and the four `agents/*/.claude/settings.json`
files. Don't take the points below on trust: check each one in the code and run `python3 -m unittest` (it includes
the tests that try to get round the sign-off). Then tell the person what you found in plain English, a sentence or
two each, and say so plainly if a point doesn't hold.

- **Where it writes.** Inside this folder: the interns' files, `team/team.json`, `team/inbox/`, `team/status/`,
  `team/logs/` and small launchers in `bin/`. Outside it, only two things. The sign-off key, made the first time they
  approve a card from the terminal: on macOS the private key goes in their keychain with no trusted apps (so every
  read asks for their Mac password) and the public half in `~/.config/agent-interns/signoff.pub`; elsewhere both are
  files in that folder, readable only by them. And, only if they connect a bank, its tokens in
  `~/.config/agent-interns/` or the keychain.
- **What leaves the computer.** Only two scripts make network calls, and only once the person has set them up:
  `team/bin/slack.py` (posts to their own private Slack channel) and `agents/arthur/tools/truelayer.py` (reads bank
  statements, read-only). Their AI tool talks to its own provider as it always does.
- **Who signs off.** Check in `team/bin/approvals.py` and `team/bin/guard.py` how only they can approve an email:
  a sign-off comes from their own terminal or their reaction on the card, each one carries evidence the guard checks
  at send time, and no intern can react, run `approve` or edit a draft they've signed off.
- **Memory stays theirs.** The interns' memory and working files stay on this computer and out of git
  (`.gitignore`, and `install.py` checks it). Keys go in the keychain or environment, never in files here.

Then give them the known limits, in your own words:

- The guard runs as a Claude Code hook. In Codex, Gemini CLI and tools without hooks, the same rules are written
  into each intern's brief, but no code enforces them.
- Scheduled runs are set up for Claude Code: tick.py hands it the team folder and the allowed tools on the command
  line. With another tool, its `runner` in `team/team.json` needs write access to the intern's folder and `team/`.
- The interns run as their user account. The guard blocks the routes it knows (approving, faking a terminal,
  stripping the AI-tool markers, reading the key, reacting, importing `approvals`), but deliberately disguised code
  could still reach what they can. For hard isolation, run the interns under a separate OS user or in a container.
- On macOS, the terminal sign-off asks for their Mac password before it signs. They should click "Allow", never
  "Always Allow": "Always Allow" trusts the `security` tool for good, and then an intern could read the key too.
- Off macOS, the private key is a file. A file readable by their user is readable by any agent running as them, so
  there the guard is the only thing between an intern and that key.
- The public key file decides which signatures count. An intern running as them could in principle swap it; the
  guard blocks writes to that folder, but only a separate OS user makes it impossible.
- Tool names are matched after lower-casing and removing separators, so `sendMail`, `send-email` and `send_email`
  count as the same, and dispatch, deliver, respond and create-a-message count as sends. A tool with a name none of
  these words cover still wouldn't be recognised: check new tools against `python3 team/bin/guard.py --test` before
  an intern gets them.
- The deny lists in `settings.json` use wildcards, which not every tool reads the same way. The guard is the catch-all.
- `verify` compares the card with the draft text the send run passes in. It can't read the mail client itself.

Then ask: "Are you comfortable for me to go ahead?" Carry on only after a clear yes. If not, answer their questions
and stop there.

## 2. Install

Check `python3 --version` is 3.9 or later. Ask three things: their first name, their business in one line, and the
goal for this quarter (they can skip it). Pass their answers as JSON on stdin, so no shell ever reads their words:

```sh
python3 install.py --yes --answers - <<'ANSWERS'
{"owner": "Sam", "business": "Bookkeeping for independent cafes", "goal": "ten new clients"}
ANSWERS
```

Write their words as JSON strings (escape quotes and backslashes). The quoted `'ANSWERS'` stops the shell expanding
anything. Add `"tool": "codex"` or `"tool": "gemini"` if that's the tool they use (Claude Code is the default when
it's installed). `python3 install.py --help` lists every option and installs nothing.

## 3. Open the head intern

The interview belongs to the head intern, in his own folder with his memory and guard, so don't run it from here.
Open a new terminal for them in this folder (on a Mac: `open -a Terminal bin/theo`), or tell them to open one and
run `python3 team/bin/open.py theo`. Use the new name if they renamed him. The first time, he starts the interview
himself; if he doesn't, they type `/onboard` (or ask for the onboarding interview in tools without slash commands).
It takes about ten minutes and fits the whole team to their business.

## 4. Later, when they want it

- The interns running on their own: the "Running on their own" section of `README.md`.
- Slack on their phone: `integrations/messaging.md`. Their bank connected: `integrations/finance/TRUELAYER.md`.

## Rules for you

- Never send, delete or pay anything on their behalf, now or later. Never approve a card or react to one.
- Don't weaken `team/bin/guard.py` or the deny lists to make something work; ask them instead.
- Keep their name, clients, figures and keys out of files git tracks. Before they share a copy of their own,
  run `python3 check_private.py`.
