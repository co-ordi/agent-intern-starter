# Finance: Arthur and your bank statements

Arthur is the most capable intern on the team because money is the one place where the data is already clean. He is
useful from day one with nothing more than a statement, and connecting your bank is an optional extra:

1. **Your bank statements, from day one.** Download a CSV from your online banking and run
   `python3 agents/arthur/tools/categorise.py statement.csv`. No account and no keys.
2. **Optionally, your bank connected.** `agents/arthur/tools/truelayer.py` fetches new statements through TrueLayer
   (UK and EU open banking), so the weekly pulse, the forecast and the tax paperwork stay current without you
   exporting anything. In the US, Plaid plays the same role.

The connection is read-only access that you approve with your bank, and you can withdraw it any time. Arthur can never
move money, and your statements are stored only on your machine.

`truelayer.py` is written against TrueLayer's Data API docs (v1, checked October 2026) and tested with mocked
responses. **Try the sandbox first**: it is the default, and TrueLayer's Mock Bank logs in as `john` / `doe`.

## The shape of it

```
your bank ──your consent──▶ TrueLayer (read-only scopes) ──▶ truelayer.py pull ──▶ out/statement.csv
                                                                                        │
                            out/money-<date>.md ◀── categorise.py (rules: categories.json) ◀┘
                                     │
                            Arthur reads it for the pulse, the forecast and tax prep
```

## Set it up (sandbox, about 15 minutes)

1. Make a free account at [console.truelayer.com](https://console.truelayer.com) and create an app. It starts in
   sandbox. Note the `client_id` and `client_secret`.
2. Keep them out of the repo. Put them in your shell profile or keychain:
   `export TRUELAYER_CLIENT_ID=... TRUELAYER_CLIENT_SECRET=...`
3. `python3 agents/arthur/tools/truelayer.py link`, open the link it prints, choose Mock Bank, log in as john / doe.
   You land on TrueLayer's redirect page with a code.
4. `python3 agents/arthur/tools/truelayer.py connect <code>`. Tokens are stored in
   `~/.config/agent-interns/truelayer-sandbox.json` with 600 permissions (or the macOS keychain with
   `TRUELAYER_KEYCHAIN=1`). Never in the repo, never in Arthur's memory.
5. `python3 agents/arthur/tools/truelayer.py pull --from 2026-04-06`, then
   `python3 agents/arthur/tools/categorise.py agents/arthur/out/statement.csv`.

When that works, add `--live` to the same commands with your live app's credentials and your real bank. To keep it
current, a daily cron line is enough: `python3 agents/arthur/tools/truelayer.py pull --live` appends the last 30
days without duplicates.

## How long consent lasts

An access token lasts an hour and the client refreshes it for you. In the UK, the connection lasts up to 90 days
(the refresh token must be used within its first 30); after that, run `link` and `connect` again. `truelayer.py
status` shows the connection's details, and `truelayer.py disconnect` deletes the stored tokens from your machine. To
withdraw the consent at the bank as well, remove TrueLayer in your bank's open banking or connected apps settings.

TrueLayer recommends its newer Data API v3 for brand-new integrations. This client speaks v1, which is fully
documented and has the Mock Bank, and its HTTP layer is one function if you move.

## Read-only, in three places

- **The scopes** are `info accounts balance transactions offline_access`. None of them can pay.
- **The code** only POSTs to the token endpoint and only GETs under `/data/v1`. Any other URL, a payments endpoint
  included, raises an error before a request is made.
- **The guard** blocks any intern's shell command that mentions a payments, mandates or payouts endpoint, and any
  tool named like a payment.

## What Arthur does with it

| Job | Output | When |
|---|---|---|
| Categorise | every transaction tagged (client income, software, travel, tax, drawings); new merchants asked about once | after each pull |
| Weekly pulse | cash today and in 4 and 13 weeks; due in; due out; one decision | Monday 08:45 |
| 13-week forecast | from invoices raised, recurring costs and the last 12 weeks' pattern | refreshed weekly |
| Invoice matching | a payment lands, the invoice is marked paid and the chaser cancelled | after each pull |
| Tax preparation | income and costs by tax year, receipts matched, a list of what's missing | monthly, and before a return |

Tax preparation means **gathering, never filing**: Arthur preps the figures for you or your accountant to submit.

## What he never does

- Move money, pay anything, or change a bank or card setting.
- Put figures in a team channel or any shared space. Numbers live in the files you open.
- Share bank statements with another intern. Sales and marketing see "a client paid" as a handoff line, never the amount.
- Store credentials, tokens or account numbers in the repo or in memory files.
