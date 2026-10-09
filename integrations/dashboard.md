# The board: where the truth lives

Every team needs one place that is the record: what is due, who said what, what got done. Your interns read and
write it; you glance at it. It can be a to-do app, a spreadsheet, a CRM, or a small dashboard you build. What
matters is that there is one, and that the interns can reach it through a tool.

## The minimum

| Thing | Example | Who writes it |
|---|---|---|
| Actions | a card with a title, due date, owner, done | you and the orchestrator (live); interns suggest (scheduled) |
| Pipeline | one row per deal: stage, last touch, next step, value | the sales intern |
| The day's outbound | today's calls, messages and emails, each with a draft and a tick | the sales intern writes, you tick |
| Content calendar | what posts when, with its hook test | the marketing intern |
| Ledger and forecast | money in, money out, the 13-week view | the finance intern (figures stay local) |
| A strategy panel | the quarter's goal, the weekly rhythm, tick boxes you tick yourself | the orchestrator writes the plan, only you tick |

## Giving the interns a tool for it

Claude Code reaches outside tools through MCP servers. Three ways in, cheapest first:

1. **Files.** A CSV or Markdown table in the repo's `team/` folder. Zero set-up; fine for one person.
2. **An existing app's MCP server.** Notion, Trello, Linear, Airtable and Google Sheets all have one. Add it to
   each intern's `.claude/settings.json` and name the tools in OPERATING.md.
3. **Your own small MCP server** over your own database. Twenty tools (list actions, create action, set stage,
   log a call, read the sheet) is a weekend, and it means the board is exactly what your business needs.

Whichever you pick, add two rules to the guard: SQL is read-only for interns (`SELECT` only), and scheduled runs
never create, complete or delete items; they suggest, in the morning report, and you say yes.
