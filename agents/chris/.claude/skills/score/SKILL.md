---
name: score
description: 📣 Chris · Friday: the week's posts, replies and saves against last week, and which hook style won.
---

# /score

Friday: posts published, replies and saves against last week, plus whatever the bigger pieces measure (sign-ups, views).

1. Make sure every post the human published this week is in out/posts.csv with its hook tag and numbers: `python3 tools/hooks.py log --date D --hook story --replies N --saves N` (ask for any number you can't read).
2. Run `python3 tools/hooks.py score`. It ranks the hook styles over four weeks and only names a winner once two styles have enough posts.
3. If it names a winner, promote it in PLAYBOOK.md's Defaults with the line it prints (the dates and the numbers are the evidence) and retire the loser. If it says too early, add the untested style to Running tests instead.
4. Three lines for the Monday brief.

Finish every run with one line in `memory/log.md` and, in a scheduled run, your contribution in `../../team/inbox/<date>/chris.md`.
