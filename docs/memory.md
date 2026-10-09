# Memory that works together

The difference between an agent and a persona is that the agent remembers. These are the rules that make four
interns' memories add up to one team that never starts from zero, and that you can read in a minute.

![How memory flows between the interns](diagrams/memory.svg)

## Each intern's memory is a file with a fixed shape

`agents/<name>/memory/MEMORY.md`, read at every start by `boot.py`:

```
# <Name> memory (read at every start; update in place, never a diary)
_Last tidied: <date>_
## Now (what's live this week)          at most 12 bullets: the current state
## People and deals                     one line each: who · relationship · status · next step · [source, date]
## Decisions and rules from your human  dated, one line each, their words where possible
## What works / lessons                 dated, evidence-backed; point to PLAYBOOK.md where the default lives
## Where things are                     files, documents, dashboards, ids
```

- **One line per fact**, newest first, ending with a source and a date in brackets.
- **Write** when the human decides something, when a fact will matter next week, or when a lesson has evidence.
- **Don't write** what the board or CRM already holds, narration, or tool output. Point to it instead.
- **Update in place.** Change the line that is out of date; don't add a new one under it.
- **Tidy weekly.** At the Friday review: merge duplicates, drop what's superseded, trim Now to this week, update the date.

Two companions: `questions.md` (open questions for the human only, each dated; the answer moves into MEMORY.md and the
question goes) and `log.md` (one terse line per run, never edited, so two machines can merge it line by line).

## The team's shared memory is a folder per day

`team/inbox/<date>/` is where the interns talk to each other and to the morning report:

| File | Written by | Read by |
|---|---|---|
| `<agent>.md` | each intern's morning run | the orchestrator, for the brief |
| `orders.json` | the orchestrator | each intern, its own orders only |
| `orders-<agent>.md` | each intern | the orchestrator and the brief |
| `handover-<client>.md` | the sales intern at signing | the orchestrator |
| anything else | one named writer | everyone, at start-up |

**One writer per file.** Two interns never edit the same file, so nothing is lost and nothing needs merging.

## Handoffs are lines in those files

A deal signed, a proposal accepted, a milestone delivered, a question prospects keep asking: each is a line in the
day's folder, from the intern that saw it to the intern that acts on it. `boot.py` loads the folder at every
start, so the handoff is seen the next time the receiving intern wakes, with no message passing and no queue. If a
handoff stalls, the orchestrator's health check chases the intern, not the human.

## The playbook is memory with evidence

`PLAYBOOK.md` holds each intern's defaults (the opener that works, the hook style that gets replies) in a table
with the date and the evidence. A default without evidence is a running test. The Friday review promotes and
retires them. This is how the team gets better rather than just older.

## Why it works

- The interns never start from zero: boot loads memory, questions, today's folder and orders before the first word.
- You can audit any intern in a minute: open its MEMORY.md.
- Memory is yours: files, in your folders, never in git, synced only through a store you control (`team/bin/memsync.md`).
- The shape is fixed, so a human and a script can both read it, and an intern that drifts into diary-writing is easy to spot.
