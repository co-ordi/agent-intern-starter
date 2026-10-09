# Connecting your tools

The head intern connects these with you during the interview, one at a time, and tests each one with a single
read-only call before moving on. You can skip any of them: every intern also works from exports in a folder.

For each tool, try the routes in this order: your AI coding tool's own built-in connector, then an MCP server made by
the product's own company, then the fallback in the last column. Check what's on offer for your tools when you
connect them; this table doesn't promise any product has a connector.

| Tool | Easiest route | Who uses it | Read or draft | Fallback |
|---|---|---|---|---|
| **Email** | Your AI tool's mail connector, or your provider's MCP server | Head intern, sales | Reads, writes drafts. Only the head intern sends, and only a card you've signed off | Paste or forward the thread |
| **Calendar** | Your AI tool's calendar connector, or your provider's MCP server | Head intern (everyone can read it) | Reads. Blocks your own time on your yes; never invites anyone | Paste the week, or an `.ics` export |
| **CRM** (contacts and deals) | The CRM's own MCP server, or its API through a small script in `agents/ella/tools/` | Sales | Reads, writes notes and stages. Never deletes | A CSV export each morning |
| **Accounting** | The accounting product's own MCP server or API | Finance | Reads, writes invoice drafts | A CSV export of invoices |
| **Bank** | A statement export (CSV) | Finance | Reads only. Never moves money | Optional: a read-only connection through `agents/arthur/tools/truelayer.py` ([integrations/finance/TRUELAYER.md](../integrations/finance/TRUELAYER.md)) |
| **Messaging** (Slack or similar) | `team/bin/slack.py`, with a bot token in your keychain or environment ([integrations/messaging.md](../integrations/messaging.md)) | Head intern posts the report and cards | Posts as the bot in your private channel. No intern posts as you | Files in `team/inbox/` |

Scheduled runs only use the tools listed under `"allow"` in `team/team.json`; the head intern adds each one after
its test. Keys and tokens go in your keychain or the AI tool's own config, never in files here. What each intern may never
touch, and how the guard enforces it, is in [tools.md](tools.md).
