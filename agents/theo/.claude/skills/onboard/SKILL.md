---
name: onboard
description: 🧭 Theo · Day one: interview the human (about a dozen plain questions, one at a time) and fit every intern to their business.
---

# /onboard

Run this on day one (when `../../team/team.json` has no `"onboarded"` date) or whenever the human asks to set up the team again. It takes about ten minutes. You're fitting four interns to one business, so listen more than you talk.

## First: the whole team, or one intern?

Before the questions, ask: "Do you want the whole team from day one, or to start with one intern for a week and add
the others once it's earned its place? Ella (sales) or Arthur (money) are the easiest to judge in a week; Chris
(marketing) works too." Either answer is fine; say so.

- **The whole team:** run everything below. If `../../team/team.json` has an `"active"` list, remove it.
- **One intern:** still run the interview, but ask only the questions that intern needs (everyone: 1, 2, 8, 9;
  sales: 3, 4, 5, 6, 7, 12; marketing: 6, 7, 10; finance: 5, 11) and connect only its tools. Set `"active"` in
  `../../team/team.json` to a list with that intern's folder name, e.g. `["ella"]`: scheduled runs then skip the
  others. They run it by hand for a week, no scheduling.
- **Adding the others later** (they open you and say "add the team", or name an intern): ask the questions you
  skipped, connect those interns' tools, then add them to `"active"`, or remove the list when everyone's on.

## The interview

Ask one question at a time, in plain words, and wait for the answer. Skip any question the human already answered. If they say "skip", leave it and move on.

1. What do you sell, and who buys it?
2. What's the one goal for this quarter? A number if you can (ten new clients, £X a month, launch the course).
3. Who are your top clients or open deals right now, and what stages does a deal go through?
4. How do new customers usually find you?
5. Which tools do you use for: contacts or deals (CRM or to-do app), email, calendar, accounting, and banking (or do you export statements)?
6. How do you sound? Paste two emails or posts you've written and liked.
7. Any words or habits you never want in your name?
8. What must never happen? (A client named in public, a discount nobody agreed, a message after 8pm.)
9. Which days and hours do you work?
10. Beyond a post a weekday, what marketing do you want: a weekly video, a newsletter, an event, or nothing yet?
11. How do invoices work: when they go out, the payment terms, and anything about money that must never be shared?
12. Anyone the team should treat with care: partners, introducers, people never to contact cold?

## Confirm before writing

Show a summary on one screen: the business in a line, the goal, the deal stages, the tools per intern, the voice in three bullets, the never list, the working hours and the schedule changes they imply. Ask "Shall I set the team up with this?" and write nothing until the human says yes. If they correct something, show the corrected line and ask again.

## Then write

1. The basics, through the installer (it swaps the old values everywhere and never touches memory):
   `python3 ../../install.py --yes --owner "<name>" --business "<one line>" --goal "<goal>" --bigger-pieces "<answer 10>" --onboarded`
2. **Each intern's AGENT.md**: under "Make this intern yours", two or three lines in the human's own words, dated. Add answer 8 to every intern's Hard limits, worded as a rule.
3. **Each intern's OPERATING.md**: the Data and Tools lines name the human's actual tools (answer 5); sales gets the deal stages (answer 3) and the channels that find customers (answer 4); finance gets the invoice terms (answer 11).
4. **Memory**: seed the "Now" section of each intern's `memory/MEMORY.md` with the goal and what's live this week, and the "People" section of sales' and your own with the clients, deals and careful contacts (answers 3 and 12), one line each, dated. Nothing about money in anyone's memory but finance's.
5. **The voice guide**: fill `../../team/voice/VOICE.md` from the pasted emails (how they open, sign off, sentence length, words they use) and add answer 7 to its never list. Quote short phrases, not whole emails.
6. **The schedule**: if the working hours (answer 9) don't fit `../../team/schedule.json`, move the jobs so the morning report lands before they start and evening jobs run before they stop. Show the change before saving it.

## Connect the tools

Once the files are written, connect the tools they named in answer 5, one at a time, in this order: email, calendar,
contacts or deals, accounting, bank. For each one:

1. **See what's already there.** Check what their AI coding tool already has connected: its connectors or MCP
   servers (in Claude Code, `claude mcp list` in a terminal or `/mcp` in a session; other tools have their own
   list). If the tool is already connected, skip to the test.
2. **Pick the simplest route,** in this order: the AI tool's own built-in connector for that product, then an MCP
   server published by the product's own company, then a CSV or export the intern reads from a folder. Say which
   route you're suggesting and why in one line. Don't promise a connector exists until you've checked.
3. **Walk them through it,** one step at a time, waiting for each step to finish. They do the logging in; you never
   see a password.
4. **Test it with one read-only call:** today's calendar events, the subject of the latest email, one contact from
   the CRM, last month's invoices. Show them what came back. If it fails, try once more, then offer the export route.
5. **Write it down** in the intern's `OPERATING.md` under Tools: the tool, the route, and whether that intern reads
   it or drafts in it (nobody sends, deletes or pays; the guard holds that). Email and calendar go to you and sales,
   contacts and deals to sales, accounting and bank to finance.
6. **Let the scheduled runs use it.** Add the names of the tools you just tested to the `"allow"` list in
   `../../team/team.json` (create the list if it's missing): scheduled runs have nobody to click allow. Reads and
   drafts only, never a send, delete or pay tool.

Never put a key or token in a file here: keys go in their keychain or the AI tool's own config. Skipping is fine:
every intern still works from exports, and `docs/connect-tools.md` has the table for later.

## Finish: how your team works

End with this, filled in from what you set up, on one screen. Write for someone who has never used a terminal: no
jargon, no file you haven't explained. Its paths are from the repo root, where they work. Then one line in
`memory/log.md`.

> **How your team works**
> - **Talk to any of them:** in a terminal in this folder, `python3 team/bin/open.py <name>` (theo, ella, chris or
>   arthur). Each one starts already up to speed: its memory, today's team notes and any orders load by themselves.
> - **Your morning report:** from me at <time> on weekdays, in `team/inbox/<date>/report.md` (and <channel>, if
>   wired). Drafts go to <their email's drafts folder>, each with a card in `team/inbox/<date>/cards.md` (or <channel>).
> - **Signing off:** a 👍 on the card, or `python3 team/bin/approvals.py approve --card <id>` in your own terminal,
>   then two minutes to change your mind. Nothing leaves without that sign-off. Before scheduling is on, the send
>   needs you too: open me and say "send it", or send the draft from your email yourself.
> - **On their own:** once scheduling is on, <who runs when, one short line from the schedule>. Switch it on with
>   the lines under "Running on their own" in the README. Until then, they work when you open them.
> - **Set up:** <tools connected>. **Still missing:** <the one thing>. **Tomorrow morning:** <what happens>.

If they started with one intern, swap the report and "on their own" lines for one: "**Each morning:** open <name>
and say <its routine, e.g. /today or /books>. When it's earning its place, open me and say 'add the team'."

You never write the human's passwords or keys anywhere; if they paste one, say so and tell them to keep it in their keychain instead.
