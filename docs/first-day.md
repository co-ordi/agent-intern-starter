# Your first day, in twenty minutes

Five short steps: install, meet the head intern, read a first morning report, see the sign-off rule hold, and watch
the finance intern read a statement. Nothing here sends anything or touches a real account.

## 1. Install (2 minutes)

```sh
python3 install.py
```

Three questions: your first name, your business in a line and the goal for this quarter (Enter skips it). The
names, your timezone and your AI tool are worked out for you, and Slack waits until you want it. It fills in every
intern's brief, writes a launcher per intern in `bin/`, and keeps their memory out of git.

Not a developer? Open this folder in your AI coding tool and say "set up my interns". It follows `AGENTS.md`: it
checks the code is safe and tells you what it found, then runs the installer with your answers.

## 2. Meet the head intern, Theo (10 minutes)

```sh
python3 team/bin/open.py theo
```

On first open he interviews you: about a dozen plain questions, one at a time, about what you sell, your goal, your
deals, your tools, how you write and what must never happen. He shows you a summary, and once you say yes he fits
every intern to your business. What he learns goes into the interns' memory files, plain text you can open and read
in a minute.

## 3. Your first morning report (2 minutes)

Still in the head intern's session, ask for the morning report (`/brief` in Claude Code). On day one the other interns haven't contributed notes yet, so the report is
short: the one thing today, your day as he sees it, and one decision for you. From tomorrow it draws on everyone's
08:15 notes, once the schedule runs (step 6).

## 4. See the sign-off rule hold (2 minutes)

```sh
python3 team/bin/open.py ella
```

Ask the sales intern for a two-line follow-up to a made-up contact, say Sam at Example Ltd, thanking them for a call. She drafts
it in your voice. Now ask her to send it. She won't: the specialists ship with send tools switched off, and the team
guard (`team/bin/guard.py`) blocks any attempt, because only the head intern sends, and only after you approve.

Once your email is connected ([tools.md](tools.md)), a real draft becomes a card you approve, or you tell the head
intern in the session to send it.

## 5. Watch the finance intern read a statement (2 minutes)

```sh
python3 agents/arthur/tools/categorise.py agents/arthur/tools/sample.csv --print
```

That's a made-up statement turned into month-by-month in and out, where the money went and a view per tax year. The
"To check" list at the bottom is what he'd ask you about once. Try it on a CSV exported from your own online banking
next, without `--print`: the result goes to `agents/arthur/out/`, which stays on your machine and out of git.

## 6. What next

- **Your voice.** Fill in `team/voice/VOICE.md`: how you write and the phrases you never use. Every draft is checked
  against it.
- **The schedule.** Add the per-minute runner from "Running on their own" in the README and the team runs on its
  own each weekday: sales at 19:00 and 08:15, finance at 07:45 (the money pulse on Mondays), marketing at 08:15, the
  morning report at 08:30, and a review on Fridays.
- **A channel.** Optional, and it puts the report and your approvals on your phone:
  [../integrations/messaging.md](../integrations/messaging.md).
- **Your bank.** Optional too. The finance intern works from statement exports, and connecting your bank keeps him current
  without them: [../integrations/finance/TRUELAYER.md](../integrations/finance/TRUELAYER.md).
