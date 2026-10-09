# Messaging: the report on your phone, drafts you sign off from anywhere

A channel is optional. Without one, the interns report in files, draft cards land in `team/inbox/<date>/cards.md`,
and you sign off from your own terminal (`python3 team/bin/approvals.py approve --card C`). Everything still works.
With a channel, the team fits in your pocket.

## Why Slack works so well here

- **The morning report lands on your phone**, so you know the plan before you sit down.
- **Drafts arrive as cards.** The exact text of an email an intern wants to send, which you approve from anywhere.
- **You answer in the thread.** "Make it shorter", "hold until Monday": the card's intern reads the thread on its next
  run and posts the new version.
- **One quiet channel instead of five dashboards.** Pings are capped at a number you choose, and only for what needs
  you.

## What ships

`team/bin/slack.py` is the Slack script: standard library only, three calls.

1. `post` a message or a card to one private channel (or a thread in it),
2. `inbox`: your messages and thread replies since a timestamp,
3. `reactions` on one message (who reacted, with what).

`team/bin/approvals.py` holds the sign-off state machine and uses `slack.py` when `team/team.json` names a channel.
`team/bin/tick.py`, run every minute (see "Running on their own" in the README), reads your reactions on open cards
and starts the head intern's send run for each card whose two minutes are up. Every command takes `--dry`, so you
can try it before the token exists: `python3 team/bin/slack.py post --text "hello" --dry`.

## Set-up (Slack)

- A Slack app in your own workspace with a bot token and the scopes `chat:write`, `reactions:read`,
  `channels:history` and `groups:history` (the last one for a private channel).
- One private channel: you and the bot. Nothing else reads it.
- The token in your environment as `TEAM_SLACK_TOKEN`, or in your macOS keychain
  (`security add-generic-password -s agent-interns-slack -a team -w`, which prompts for it). Never in a file.
- In `team/team.json`: `"slack_channel"` (the channel id, `C…`) and `"slack_owner"` (your Slack user id, `U…`), so
  only your own reaction counts as a sign-off.

## Any channel works

Slack is the one that ships, not a requirement. Microsoft Teams, Discord, Telegram, WhatsApp Business or plain email
(a reply that says "approve" standing in for the reaction) can carry the team: write `team/bin/<channel>.py` with the
same three functions against that channel's API, and point the two `import slack` lines in `approvals.py` at it. Each
needs the same three things: a bot or app identity, one private conversation, and a token kept outside the repo.

## What flows through it

| Direction | What | Who |
|---|---|---|
| To you | The morning report | The head intern |
| To you | Draft cards: the exact text of an email an intern wants to send | Any intern, through `approvals.py card` |
| To you | A ping, up to the daily cap in `team/TEAM.md`, only for: a client or partner reply that needs you, a deal at risk, a meeting within the hour with no prep, a payment problem | The intern that saw it |
| From you | Your sign-off: a thumbs-up reaction on a draft card. The send waits two minutes; remove the reaction to cancel | `tick.py`, every minute |
| From you | A reply in a card's thread: an edit, a question, "hold" | The card's intern, on its next run, posts the new version |

Rules: interns post only through the team's script, never through a connector that posts as you. Finance posts no
figures. A typed "send" in the channel is not a sign-off, and a sign-off on an older version of a card doesn't count.
