---
name: books
description: 💷 Arthur · Weekday mornings: pick up any new bank statement, categorise it, and list what needs the human's eye.
---

# /books

Weekday mornings (Monday's /pulse does this itself): keep the books current without anyone asking.

1. If the bank is connected, run `python3 tools/truelayer.py pull`; it only adds transactions it hasn't seen. If not, look for a statement export in out/ newer than the last one in `memory/log.md`. Nothing new: one line in the log and stop.
2. Run `python3 tools/categorise.py` on the statement and read its "To check" list.
3. Add a rule to tools/categories.json only for a merchant you're sure of (the same one explained before). Everything else stays in "To check" for the human.
4. An invoice now past its terms goes in your contribution as a line for /chase, with the client's name and no amount.

Never move money, pay, or contact anyone. Figures stay in out/; the team notes get words, not numbers.

Finish every run with one line in `memory/log.md` and, in a scheduled run, your contribution in `../../team/inbox/<date>/arthur.md`.
