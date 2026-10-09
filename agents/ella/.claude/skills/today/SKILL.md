---
name: today
description: 🚀 Ella · Build or refresh the outbound sheet for the day given in `$ARGUMENTS` (default today).
---

# /today

Build or refresh the outbound sheet for the day given in `$ARGUMENTS` (default today).

In the morning run, check replies first: everyone on the sheet or in follow-ups who has replied since the last run moves off the cold lanes and into follow-ups, with a draft answer for the human (never sent). A reply that needs the human today goes at the top of your contribution.

Lanes: calls, messages, emails, each sized to the day's targets in OPERATING.md, plus the follow-ups that matter. For every item: why them, why now, the draft, the channel. Before anyone goes on as a new contact, run `python3 tools/contacted.py check --email <address>` (or --name): LIVE means a follow-up, HOLD or NO means leave them off, WARM means a warm message, never a cold one. Log every touch your human confirms with `contacted.py log`. Before building, read yesterday's sheet in out/: anything your human moved, cut or added by hand is a signal; when the same pattern shows twice, add it to PLAYBOOK.md with the dates. Write the counts to ../../team/status/ella.line and a 3-line contribution to ../../team/inbox/<date>/ella.md, as the human's actions with a time.

Finish every run with one line in `memory/log.md` and, in a scheduled run, your contribution in `../../team/inbox/<date>/ella.md`.
