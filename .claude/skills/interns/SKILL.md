---
name: interns
description: Your AI interns. Lists the team, what each one is for, and how to open one. Use when you type /interns or ask which intern does what.
---

# /interns

Read `team/team.json` (or each `agents/*/agent.json`) and show the team as a short table: name, role, one line on
what it owns (from its AGENT.md "What you own"), and how to open it (`bin/<name>`, or a terminal in `agents/<name>`).
Then, if a job was mentioned, say which intern it belongs to and why, in one line. Never do the intern's job here.
