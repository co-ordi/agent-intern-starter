# Wiring: how the pieces talk

No framework, no server, no queue. Files, hooks and cron, held together by a few small Python scripts you can read
in an afternoon. This is the whole diagram.

![A day in the team](diagrams/day.svg)

## The pieces

| Piece | What it is | Where |
|---|---|---|
| An intern | A folder your AI coding tool opens: `AGENTS.md` (or `CLAUDE.md` for Claude Code) → `AGENT.md` (who), `OPERATING.md` (what, when, with what), `PLAYBOOK.md` (defaults with evidence), `memory/`, `.claude/settings.json` (hooks, tool permissions), `.claude/skills/` (its slash commands) | `agents/<name>/` |
| Hooks | Claude Code runs a command at SessionStart (`boot.py`), before every tool call (`guard.py`) and, for the orchestrator, on every prompt (`send_ok.py`) | each intern's settings.json |
| The team folder | Shared rules, the schedule, the day's notes, run status and logs | `team/` |
| The scripts | open, boot, guard, orders, brief, tick, approvals, slack, voice, send_ok | `team/bin/` |
| The schedule | Which intern runs which skill at what time | `team/schedule.json`, run by `tick.py` every minute from cron or launchd |

## A day

1. **Overnight (19:00)** the sales intern's scheduled run builds tomorrow's outbound sheet and writes a
   three-line contribution to `team/inbox/<tomorrow>/ella.md`. The guard is in scheduled mode: drafts only.
2. **08:15** the sales and marketing interns run: replies since last night, today's sheet, three post options.
   Each writes its contribution. The finance intern has already picked up any new statement at 07:45 (the money
   pulse instead on Mondays).
3. **08:30** the orchestrator runs `/brief`: reads the contributions, the calendar and the board, writes the brief,
   gives orders (`orders.py give`), posts the report (a file, and Slack if wired).
4. **During the day** you open an intern and work with it. `boot.py` has already loaded its memory, today's folder
   and its orders. Live, the guard relaxes for the orchestrator (it can add and tick cards) but still blocks
   deletes and unarmed sends.
5. **A draft you like:** your sign-off on its card (a reaction in your channel, or `approvals.py approve` in your
   own terminal). Two minutes later `tick.py` starts a short send run for the orchestrator, which checks the draft
   still matches the card, locks it and sends it once. Or, in a live session, tell the orchestrator to send it:
   `send_ok.py` arms one send and `guard.py` lets exactly that one through.
6. **19:30** the orchestrator runs `/health`: failed or missed runs, stale memory, an intern sounding generic.
7. **Friday** each intern scores its week against its numbers and updates its playbook with the evidence.

## The two modes

| | Live (you in the terminal) | Scheduled (`tick.py`, `TEAM_RUN=1`) |
|---|---|---|
| Sends | Orchestrator only, after your message arms it or for a card you signed off | Only a card you signed off, once, after the two minutes (and only under Claude Code's hooks) |
| Deletes | Never | Never |
| Board | Orchestrator adds and ticks; others suggest | Everyone suggests, in the report |
| Calendar | Blocks of your time on your yes | Blocks only, no invites |
| Posting as you | Never | Never |

## Why files

- You can read everything the team knows with `cat`.
- Nothing runs unless the per-minute runner or you start it, so a quiet team costs nothing.
- Git tracks the rules and the code; your data stays out of it (`.gitignore`, `check_private.py`).
- Any piece can be swapped: a different model for a cheap job, a different mail tool, your own board.
