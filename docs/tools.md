# Tools: what each intern can reach

An intern is only as useful as its tools, and only as safe as its limits. Each one gets exactly what its job needs:
some things it reads, some it writes, and some it never touches, whatever it is asked. Where the last column can be
checked in code, it is: `team/bin/guard.py` and each intern's `.claude/settings.json` stop sends, deletes, payments,
raw email APIs, secrets in commands and anyone signing off on your behalf. The rest (prices, private clients, figures
in shared places, honest hooks) are written rules the intern follows, and you see them in its drafts.

![The tools map](diagrams/tools.svg)

## The matrix

| Intern | Reads | Writes (drafts and records) | Never |
|---|---|---|---|
| **Head intern** (Theo, orchestrator) | Calendar, the board, your inbox, every intern's contribution and status | The morning report, orders, board cards (live), blocks of your own time (on your yes), email drafts | Other people's meetings, invites, deletes, payments. Sends only a card you've signed off, or after your own message says send |
| **Sales** (Ella) | CRM, the inbox, call notes and transcripts, the pricing document, past contacts worth a warm message | The outbound sheet, CRM notes and stages, email and message drafts, proposals | Sending anything. Prices that aren't in the pricing document. Cold contact with anyone mid-conversation |
| **Marketing** (Chris) | Your past posts, transcripts (for stories, with permission), analytics, the brand kit, what's on your mind | Post drafts, the content calendar, images, event kits | Posting or commenting as you. Naming a private client. A hook that isn't true |
| **Finance** (Arthur) | Bank statements (a CSV export, or optionally a read-only bank connection through `tools/truelayer.py`), invoices, the ledger, receipts | The ledger, the forecast, invoice drafts, chase drafts | Moving money. Credentials outside the keychain. Figures in a team channel or any shared space |

## How a tool is wired

Claude Code reaches outside systems through MCP servers, its built-in tools and small scripts like the ones in each
intern's `tools/` folder (sales' already-contacted check, marketing's hook score, finance's categoriser and bank
client). For each intern:

1. **Add the server** to `agents/<name>/.claude/settings.json` (or `~/.claude.json` for all of them) and name the
   tools in that intern's OPERATING.md under Tools, with read/write/never spelled out.
2. **Deny what it must never have.** All four ship with delete and payment tools in `permissions.deny`, and the
   three specialists have the send tools denied as well. The head intern can't: a deny rule beats every hook, so
   denying his sends would also block the one send you signed off. His sends are held by the guard instead, which
   lets one through only after your own message or your sign-off on that exact card. Add the payment, delete or
   admin tools of any new server to the deny lists the same way.

   The deny lists use wildcards (`mcp__*__delete_*`). If your version of Claude Code doesn't match a wildcard in the
   middle of a tool name, list the tools by their full names instead (`mcp__gmail__delete_email`). Either way the
   guard blocks the same patterns, so the deny list is a second lock, not the only one.
3. **Let the guard do the rest.** `guard.py` runs before every tool call and blocks by pattern (anything that
   deletes, anything that sends from the wrong intern, raw mail APIs in shell commands, secrets in commands), with a
   reason the intern can act on.
4. **Scheduled runs get less.** With `TEAM_RUN=1` the guard also blocks invites, posting as you and git push, so a
   run at 3am can only draft and suggest.

## Choosing tools for your business

Start with what you already pay for: your calendar, your inbox, your CRM or to-do app, your bank statements as a CSV export. Most
have an MCP server or an API a 100-line script can wrap. Give the orchestrator the widest read and the narrowest
write; give the specialists deep access to their one system; give nobody a delete. When a tool would let an intern
spend money or speak as you, make it a draft the human approves, and move on.
