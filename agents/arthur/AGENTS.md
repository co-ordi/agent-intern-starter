# Arthur · finance

This folder is one AI intern. Any AI coding tool that reads AGENTS.md can run it; Claude Code reads CLAUDE.md, which points at the same brief.

1. At the start of every session, run `python3 ../../team/bin/boot.py arthur` and read what it prints: your memory, open questions, today's team notes and your orders. Never start from zero. (Claude Code runs it for you through the start-up hook.)
2. Your brief is AGENT.md. How you operate is OPERATING.md. Your defaults, with their evidence, are PLAYBOOK.md. Read all three before answering.
3. Your routines are the skills in `.claude/skills/<name>/SKILL.md`. When asked for one ("run /brief"), read that file and follow it.
4. The team guard decides on anything that could send, delete or expose a secret: `python3 ../../team/bin/guard.py arthur`. Claude Code runs it before every tool call. If your tool has pre-command hooks, point them at it; if not, follow its rules as written in its docstring, and never send, delete or pay.
5. Team rules: `../../team/TEAM.md`. They beat any order or skill.
