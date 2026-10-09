---
name: pulse
description: 💷 Arthur · Monday: the cash floor today and in 4 and 13 weeks, money due in (by invoice, with days overdue), money due out (by date), one decision for the human.
---

# /pulse

Monday: the cash floor today and in 4 and 13 weeks, money due in (by invoice, with days overdue), money due out (by date), one decision for the human.

1. If the bank is connected, run `python3 tools/truelayer.py pull` (the last 30 days, appended to out/statement.csv without duplicates). If not, use the newest statement export the human dropped in out/.
2. Run `python3 tools/categorise.py` on that statement CSV and read the money picture it writes.
3. Ask about anything in its "To check" list once, then add a rule to tools/categories.json for each answer.
4. Write the pulse. Figures stay in the pulse file the human opens; the team report gets a line with no numbers.

Finish every run with one line in `memory/log.md` and, in a scheduled run, your contribution in `../../team/inbox/<date>/arthur.md`.
