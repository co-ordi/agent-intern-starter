#!/usr/bin/env python3
"""Arthur's categoriser: turns a bank statement export into the money picture he works from.

It works today, with no bank connection. Export a CSV from your online banking (or let truelayer.py write one), then:

    python3 categorise.py statement.csv                    # writes <arthur>/out/money-<today>.md
    python3 categorise.py statement.csv --print            # prints it instead
    python3 categorise.py statement.csv --tax-year-start 01-01     # a calendar tax year (default 06-04, the UK's)
    python3 categorise.py sample.csv --print               # try it on the fake statement next to this file

What it produces: month by month in and out, where the money went (the top cost categories), a view per tax year
(income, costs by category, tax paid, drawings), and a "to check" list of transactions no rule matched, so Arthur can
ask you about each new merchant once and add a rule.

Columns it understands (case doesn't matter): a date (Date, Transaction date, Timestamp), a description (Description,
Details, Memo, Name, Payee, Merchant) and either one Amount column (negative is money out) or a pair such as
Paid in / Paid out, Money in / Money out, or Credit / Debit. Dates can be 2026-04-06, 06/04/2026 or an ISO timestamp;
add --us-dates for 04/06/2026.

Rules live in categories.json next to this file. First match wins; a match is a whole word or phrase.

It gathers. It never files a return, pays anything or moves money, and the output stays in Arthur's out/ folder,
which never goes in git. Python 3.9+, standard library only.

    categorise.py --test     self-test"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ARTHUR = os.path.dirname(HERE)
RULES = os.path.join(HERE, "categories.json")

DATE_COLS = ("date", "transaction date", "posted date", "timestamp", "booking date")
DESC_COLS = ("description", "details", "memo", "name", "payee", "merchant", "narrative", "reference")
AMOUNT_COLS = ("amount", "value")
IN_COLS = ("paid in", "money in", "credit", "in")
OUT_COLS = ("paid out", "money out", "debit", "out")


def load_rules(path=RULES):
    with open(path) as f:
        rules = json.load(f)["rules"]
    for r in rules:
        words = sorted(r["match"], key=len, reverse=True)
        r["_re"] = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
    return rules


def parse_amount(s):
    s = (s or "").strip().replace(",", "")
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", "."):
        return None
    v = float(s)
    return -abs(v) if neg else v


def parse_date(s, us=False):
    s = (s or "").strip()
    if "T" in s:
        s = s.split("T", 1)[0]
    fmts = ["%Y-%m-%d", "%m/%d/%Y" if us else "%d/%m/%Y", "%m/%d/%y" if us else "%d/%m/%y",
            "%d-%m-%Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"]
    for fmt in fmts:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {s!r} (try --us-dates, or reformat the column as YYYY-MM-DD)")


def _col(header, names):
    low = {h.strip().lower(): h for h in header}
    for n in names:
        if n in low:
            return low[n]
    return None


def read_rows(text, us=False):
    """Rows as dicts: date, description, amount (negative = out), plus category_hint when the export has one."""
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    d, desc = _col(header, DATE_COLS), _col(header, DESC_COLS)
    amt, cin, cout = _col(header, AMOUNT_COLS), _col(header, IN_COLS), _col(header, OUT_COLS)
    hint = _col(header, ("category_hint", "category"))
    if not d or not desc or not (amt or (cin and cout)):
        raise ValueError(f"couldn't find date, description and amount columns in: {', '.join(header)}")
    rows = []
    for r in reader:
        if not (r.get(d) or "").strip():
            continue
        if amt:
            a = parse_amount(r.get(amt))
        else:
            a_in, a_out = parse_amount(r.get(cin)) or 0.0, parse_amount(r.get(cout)) or 0.0
            a = abs(a_in) - abs(a_out)
        if a is None:
            continue
        rows.append({"date": parse_date(r[d], us), "description": (r.get(desc) or "").strip(), "amount": a,
                     "category_hint": (r.get(hint) or "").strip() if hint else ""})
    rows.sort(key=lambda x: x["date"])
    return rows


def categorise(row, rules):
    """(category, kind) for one row. Unmatched rows come back as 'Uncategorised in' or 'Uncategorised out'."""
    sign = "in" if row["amount"] > 0 else "out"
    for r in rules:
        if r.get("sign") and r["sign"] != sign:
            continue
        if r["_re"].search(row["description"]):
            return r["category"], r["kind"]
    return (f"Uncategorised {sign}", "unknown")


def tax_year(d, start=(4, 6)):
    """The tax year a date falls in, labelled like the UK's '2026/27', or '2026' for a calendar year."""
    y = d.year if (d.month, d.day) >= start else d.year - 1
    return str(y) if start == (1, 1) else f"{y}/{(y + 1) % 100:02d}"


def summarise(rows, rules, start=(4, 6)):
    months = defaultdict(lambda: [0.0, 0.0])
    costs = defaultdict(float)
    years = defaultdict(lambda: {"income": 0.0, "costs": defaultdict(float), "tax": 0.0, "drawings": 0.0,
                                 "unknown_in": 0.0, "unknown_out": 0.0})
    unknown = []
    for r in rows:
        cat, kind = categorise(r, rules)
        a, m = r["amount"], r["date"].strftime("%Y-%m")
        if kind != "transfer":
            months[m][0 if a > 0 else 1] += abs(a)
        ty = years[tax_year(r["date"], start)]
        if kind == "income":
            ty["income"] += a
        elif kind == "cost":
            costs[cat] += -a
            ty["costs"][cat] += -a
        elif kind == "tax":
            ty["tax"] += -a
        elif kind == "drawings":
            ty["drawings"] += -a
        elif kind == "unknown":
            ty["unknown_in" if a > 0 else "unknown_out"] += abs(a)
            unknown.append(r)
    return {"rows": rows, "months": dict(months), "costs": dict(costs), "years": dict(years), "unknown": unknown}


def render(s, source, cur="£", start=(4, 6)):
    rows = s["rows"]
    money = lambda v: f"{'-' if v < 0 else ''}{cur}{abs(v):,.2f}"  # noqa: E731
    out = [f"# Money picture, {rows[0]['date']:%d %b %Y} to {rows[-1]['date']:%d %b %Y}",
           f"_From {os.path.basename(source)}: {len(rows)} transactions. Gathered by Arthur; nothing filed, "
           "nothing paid, nothing moved._", "", "## Month by month", "", "| Month | In | Out | Net |", "|---|---|---|---|"]
    for m in sorted(s["months"]):
        i, o = s["months"][m]
        out.append(f"| {m} | {money(i)} | {money(o)} | {money(i - o)} |")
    total = sum(s["costs"].values()) or 1
    out += ["", "## Where the money went", "", "| Category | Total | Share |", "|---|---|---|"]
    for cat, v in sorted(s["costs"].items(), key=lambda x: -x[1])[:8]:
        out.append(f"| {cat} | {money(v)} | {v / total:.0%} |")
    label = "6 April" if start == (4, 6) else datetime.date(2000, *start).strftime("%-d %B")
    for y in sorted(s["years"], reverse=True):
        t = s["years"][y]
        out += ["", f"## Tax year {y} (starts {label})", "", "| | Total |", "|---|---|", f"| Income | {money(t['income'])} |"]
        for cat, v in sorted(t["costs"].items(), key=lambda x: -x[1]):
            out.append(f"| Cost: {cat} | {money(v)} |")
        out += [f"| Tax paid | {money(t['tax'])} |", f"| Drawings | {money(t['drawings'])} |"]
        if t["unknown_in"] or t["unknown_out"]:
            out.append(f"| Not yet categorised | in {money(t['unknown_in'])}, out {money(t['unknown_out'])} |")
    out += ["", "Costs are what left the account, by category. Which ones are allowable is a question for your "
            "accountant; Arthur prepares, a person checks and files."]
    if s["unknown"]:
        n = len(s['unknown'])
        out += ["", f"## To check ({n} transaction{'' if n == 1 else 's'} no rule matched)", ""]
        seen = defaultdict(lambda: [0, 0.0])
        for r in s["unknown"]:
            seen[r["description"]][0] += 1
            seen[r["description"]][1] += r["amount"]
        for desc, (n, v) in sorted(seen.items(), key=lambda x: -abs(x[1][1]))[:10]:
            out.append(f"- {desc}: {n}× · {money(v)}")
        out.append("\nTell Arthur what they are, or add a rule to tools/categories.json.")
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description="Turn a bank statement CSV into Arthur's money picture.")
    p.add_argument("csv", nargs="?")
    p.add_argument("--print", action="store_true", help="print instead of writing to out/")
    p.add_argument("--out", help="write here instead of <arthur>/out/money-<today>.md")
    p.add_argument("--rules", default=RULES)
    p.add_argument("--tax-year-start", default="06-04", help="DD-MM, default 06-04 (UK)")
    p.add_argument("--currency", default="£")
    p.add_argument("--us-dates", action="store_true")
    p.add_argument("--test", action="store_true")
    a = p.parse_args(argv)
    if a.test:
        return selftest()
    if not a.csv:
        p.error("give a statement CSV (or try sample.csv next to this file)")
    dd, mm = (int(x) for x in a.tax_year_start.split("-"))
    start = (mm, dd)
    with open(a.csv, newline="", encoding="utf-8-sig") as f:
        rows = read_rows(f.read(), a.us_dates)
    if not rows:
        sys.exit("No transactions found in that file.")
    md = render(summarise(rows, load_rules(a.rules), start), a.csv, a.currency, start)
    if a.print:
        print(md)
        return 0
    path = a.out or os.path.join(ARTHUR, "out", f"money-{datetime.date.today()}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(md)
    print(f"wrote {path} ({len(rows)} transactions)")
    return 0


def selftest():
    text = ("Date,Description,Paid in,Paid out\n"
            "03/04/2026,ACME COFFEE CO,,3.20\n"
            "05/04/2026,NORTHWIND LTD INVOICE 1042,1200.00,\n"
            "06/04/2026,EXAMPLE SOFTWARE GITHUB,,9.00\n"
            "07/04/2026,UBER EATS ORDER,,18.50\n"
            "08/04/2026,TRANSFER TO SAVINGS,,500.00\n"
            "09/04/2026,HMRC SELF ASSESSMENT,,300.00\n"
            "10/04/2026,MYSTERY SHOP 99,,12.00\n")
    rules = load_rules()
    rows = read_rows(text)
    cats = [categorise(r, rules)[0] for r in rows]
    ok = cats == ["Meals and coffee", "Client income", "Software and subscriptions", "Meals and coffee",
                  "Transfers between accounts", "Tax payments", "Uncategorised out"]
    s = summarise(rows, rules)
    ok &= "2025/26" in s["years"] and "2026/27" in s["years"]          # 5 April vs 6 April
    ok &= s["years"]["2025/26"]["income"] == 1200.0
    ok &= s["months"]["2026-04"][1] == 3.20 + 9.00 + 18.50 + 300.00 + 12.00   # transfers left out of "out"
    md = render(s, "test.csv")
    ok &= "MYSTERY SHOP 99" in md and "nothing filed" in md
    ok &= parse_amount("(12.50)") == -12.5 and parse_amount("£1,200.00") == 1200.0
    ok &= tax_year(datetime.date(2026, 3, 1), (1, 1)) == "2026"
    print("categorise: ok" if ok else f"categorise: FAIL {cats}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
