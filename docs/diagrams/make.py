#!/usr/bin/env python3
"""Draws the README diagrams as SVG. One palette, one style, no drawing tool needed:
    python3 docs/diagrams/make.py          # rewrites every .svg in this folder
Edit the data at the bottom (names, roles, lines) and run it again after `install.py` renames your interns.
The portraits come from avatars/<role>.jpg (orchestrator, sales, marketing, finance), about 340 px square: swap in
your own and run it again. They're embedded in the SVGs, so the diagrams show anywhere, GitHub included."""
import base64
import os

BG, INK, CREAM, GOLD, MINT, MUTED, RED = "#161616", "#161616", "#F6EEDC", "#F2C14E", "#3ED598", "#5C5447", "#D9534F"
FONT = "Inter, Helvetica, Arial, sans-serif"
HERE = os.path.dirname(os.path.abspath(__file__))


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.parts, self.defs = w, h, [], []

    def portrait(self, x, y, size, path, shadow):
        """A square portrait in a rounded card with an offset shadow, like the hero image."""
        cid = f"c{len(self.defs)}"
        self.defs.append(f"<clipPath id='{cid}'><rect x='{x}' y='{y}' width='{size}' height='{size}' rx='28'/></clipPath>")
        self.card(x + 6, y + 6, size, size, shadow, shadow, 28)
        self.parts.append(f"<rect x='{x}' y='{y}' width='{size}' height='{size}' rx='28' fill='{CREAM}'/>")
        if os.path.isfile(path):
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            self.parts.append(f"<image href='data:image/jpeg;base64,{data}' x='{x}' y='{y}' width='{size}' "
                              f"height='{size}' clip-path='url(#{cid})' preserveAspectRatio='xMidYMid slice'/>")

    def avatar(self, x, y, size, role, ring=GOLD):
        """A round portrait from avatars/<role>.jpg, or a plain disc if there isn't one."""
        cid = f"c{len(self.defs)}"
        r = size / 2
        self.defs.append(f"<clipPath id='{cid}'><circle cx='{x + r}' cy='{y + r}' r='{r}'/></clipPath>")
        self.parts.append(f"<circle cx='{x + r}' cy='{y + r}' r='{r + 3}' fill='{ring}'/>")
        path = os.path.join(HERE, "avatars", f"{role}.jpg")
        if os.path.isfile(path):
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            self.parts.append(f"<image href='data:image/jpeg;base64,{data}' x='{x}' y='{y}' width='{size}' "
                              f"height='{size}' clip-path='url(#{cid})' preserveAspectRatio='xMidYMid slice'/>")
        else:
            self.parts.append(f"<circle cx='{x + r}' cy='{y + r}' r='{r}' fill='{MUTED}'/>")

    def text(self, x, y, s, size=13, weight=400, fill=INK, anchor="start"):
        s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.parts.append(f"<text x='{x}' y='{y}' font-size='{size}' font-weight='{weight}' fill='{fill}' "
                          f"text-anchor='{anchor}'>{s}</text>")

    def card(self, x, y, w, h, shadow=GOLD, fill=CREAM, r=14):
        self.parts.append(f"<rect x='{x+6}' y='{y+6}' width='{w}' height='{h}' rx='{r}' fill='{shadow}'/>")
        self.parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{r}' fill='{fill}'/>")

    def pill(self, x, y, w, h, fill=GOLD):
        self.parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='{h//2}' fill='{fill}'/>")

    def arrow(self, x1, y1, x2, y2, color=GOLD):
        mark = "m" if color == MINT else "a"
        self.parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' stroke-width='2.5' "
                          f"marker-end='url(#{mark})'/>")

    def line(self, x1, y1, x2, y2, color=MUTED, width=2):
        self.parts.append(f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' stroke-width='{width}' "
                          "stroke-linecap='round'/>")

    def dot(self, x, y, r=10, fill=GOLD):
        self.parts.append(f"<circle cx='{x}' cy='{y}' r='{r}' fill='{fill}'/>")

    def chip(self, x, y, color):
        self.parts.append(f"<rect x='{x}' y='{y}' width='8' height='16' rx='3' fill='{color}'/>")

    def title(self, t, sub):
        self.text(40, 54, t, 30, 800, CREAM)
        self.text(40, 82, sub, 14, 400, GOLD)

    def save(self, name):
        head = (f"<svg xmlns='http://www.w3.org/2000/svg' width='{self.w}' height='{self.h}' "
                f"viewBox='0 0 {self.w} {self.h}' font-family='{FONT}'>"
                f"<rect width='{self.w}' height='{self.h}' rx='18' fill='{BG}'/>"
                "<defs><marker id='a' markerWidth='10' markerHeight='10' refX='8' refY='5' orient='auto'>"
                f"<path d='M0,0 L10,5 L0,10 z' fill='{GOLD}'/></marker>"
                "<marker id='m' markerWidth='10' markerHeight='10' refX='8' refY='5' orient='auto'>"
                f"<path d='M0,0 L10,5 L0,10 z' fill='{MINT}'/></marker>" + "".join(self.defs) + "</defs>")
        with open(os.path.join(HERE, name), "w") as f:
            f.write(head + "".join(self.parts) + "</svg>\n")


def team(interns):
    s = Svg(1200, 830)
    s.title("Your AI interns", "you, a head intern who orchestrates, three specialists, and the memory they share")
    s.pill(520, 100, 160, 48)
    s.text(600, 132, "You", 20, 800, INK, "middle")
    # one straight line from you to the head intern, what goes each way written either side of it
    s.line(600, 148, 600, 208, CREAM, 2.5)
    s.text(586, 183, "↑ the morning report, draft cards", 12, 700, MINT, "end")
    s.text(614, 183, "your sign-off, replies, decisions ↓", 12, 700, GOLD)

    def card(x, y, w, it, shadow):
        s.card(x, y, w, 190, shadow)
        s.avatar(x + 20, y + 20, 80, it["key"])
        s.text(x + 118, y + 44, it["title"].upper(), 12, 800, MUTED)
        s.text(x + 118, y + 72, it["name"], 24, 800)
        s.text(x + 118, y + 96, it["tag"], 14)
        s.line(x + 20, y + 118, x + w - 20, y + 118, "#E2D6BC", 1)
        s.text(x + 20, y + 140, "TOOLS", 10, 800, MUTED)
        s.text(x + 20, y + 158, it["tools"][0], 13)
        s.text(x + 20, y + 177, it["tools"][1], 13, 400, MUTED)

    card(390, 208, 420, interns[0], MINT)
    # an org chart: one line down from the head intern to a bus, then a straight drop to each specialist
    xs = (40, 430, 820)
    bus = 432
    s.line(600, 404, 600, bus, CREAM, 2.5)
    s.line(xs[0] + 170, bus, xs[-1] + 170, bus, CREAM, 2.5)
    for x, it in zip(xs, interns[1:]):
        s.line(x + 170, bus, x + 170, 472, CREAM, 2.5)
        card(x, 472, 340, it, GOLD)
    s.text(405, 456, "orders ↓", 13, 700, GOLD, "middle")
    s.text(795, 456, "notes and handoffs ↑", 13, 700, MINT, "middle")

    s.card(40, 696, 1120, 104, MUTED, CREAM, 12)
    for x in (210, 600, 990):
        s.line(x, 668, x, 694, MUTED, 2)
    s.text(60, 726, "Shared memory", 17, 800)
    s.text(200, 726, "every intern reads it at start-up (boot.py) and writes only its own files", 12, 400, MUTED)
    files = [("team/TEAM.md", "the rules"), ("team/schedule.json", "who runs when"),
             ("team/inbox/<date>/", "notes, orders, handoffs"), ("agents/*/memory/", "what each one remembers")]
    for i, (name, what) in enumerate(files):
        x = 60 + i * 275
        s.text(x, 760, name, 13, 700)
        s.text(x, 780, what, 12, 400, MUTED)
    s.save("team.svg")


def team_row(interns):
    """The four portraits in a row, role on top, name beneath: the README's team header."""
    s = Svg(1600, 540)
    for i, it in enumerate(interns):
        cx = 200 + i * 400
        path = os.path.join(HERE, "avatars", f"{it['key']}.jpg")
        s.portrait(cx - 170, 40, 340, path, MINT if i in (0, 3) else GOLD)
        s.parts.append(f"<text x='{cx}' y='440' font-size='24' font-weight='700' fill='{GOLD}' text-anchor='middle' "
                       f"letter-spacing='2'>{it['role'].upper()}</text>")
        s.text(cx, 494, it["name"], 46, 800, CREAM, "middle")
    s.save("team-row.svg")


def day():
    s = Svg(1000, 330)
    s.title("A day in the team", "cron runs the schedule; you open an intern when you want one")
    beats = [("19:00", "sales", "lines up tomorrow"), ("07:45", "finance", "new statements"),
             ("08:15", "sales · marketing", "replies, post options"), ("08:30", "the head intern", "the morning report"),
             ("day", "you", "work, sign off drafts"), ("Friday", "everyone", "score the week")]
    x0, step = 100, 160
    for i, (when, who, what) in enumerate(beats):
        x = x0 + i * step
        s.dot(x, 150, 10, MINT if who == "you" else GOLD)
        if i < len(beats) - 1:
            s.line(x + 14, 150, x + step - 14, 150)
        s.text(x, 126, when, 15, 800, CREAM, "middle")
        s.text(x, 188, who, 13, 700, GOLD, "middle")
        s.text(x, 210, what, 12, 400, CREAM, "middle")
    s.text(40, 272, "Scheduled runs are headless: they draft and suggest. The only send is a card you've signed off.", 12, 400, CREAM)
    s.text(40, 296, "Everything the team knows is a file you can open.", 12, 700, MINT)
    s.save("day.svg")


def tools(interns):
    s = Svg(1100, 520)
    s.title("What each intern can reach", "reads · writes (drafts and records) · never")
    for i, it in enumerate(interns):
        x = 40 + i * 262
        s.card(x, 110, 240, 360, MINT if i == 0 else GOLD)
        s.text(x + 16, 142, it["role"].capitalize(), 20, 800)
        s.text(x + 16, 162, it["name"] + (" · orchestrator" if i == 0 else ""), 12, 400, MUTED)
        y = 184
        for label, color, items in (("Reads", MINT, it["reads"]), ("Writes", GOLD, it["writes"]), ("Never", RED, it["never"])):
            s.chip(x + 16, y - 7, color)
            s.text(x + 32, y + 6, label, 13, 700)
            for j, item in enumerate(items):
                s.text(x + 32, y + 26 + j * 17, item, 12, 400, MUTED)
            y += 26 + len(items) * 17 + 14
    s.text(40, 500, "Only the head intern can send: a card you've signed off, or after your own message says send. Nobody deletes or pays.", 12, 400, CREAM)
    s.save("tools.svg")


def memory(interns):
    s = Svg(1000, 560)
    s.title("Memory that works together", "each intern remembers in a file with a fixed shape; the team talks through a folder per day")
    for i, it in enumerate(interns):
        x = 40 + i * 235
        s.card(x, 120, 210, 130, MINT)
        s.text(x + 18, 150, it["role"].capitalize(), 18, 800)
        s.text(x + 18, 172, f"{it['name']} · memory/MEMORY.md", 12, 400, MUTED)
        s.text(x + 18, 202, "Now · People · Decisions", 13)
        s.text(x + 18, 222, "Lessons · Where things are", 13)
        s.text(x + 18, 242, "+ questions.md · log.md", 13)
        s.arrow(x + 105, 256, x + 105, 318)
    s.card(40, 324, 920, 110, GOLD)
    s.text(58, 354, "team/inbox/<today>/", 20, 800)
    s.text(58, 378, "one writer per file · read by every intern at start-up (boot.py)", 13, 400, MUTED)
    s.text(58, 406, "<intern>.md", 13); s.text(58, 424, "contributions to the brief", 11, 400, MUTED)
    s.text(330, 406, "orders.json → orders-<intern>.md", 13); s.text(330, 424, "the plan down, reports back", 11, 400, MUTED)
    s.text(640, 406, "handover-<client>.md", 13); s.text(640, 424, "a deal signed → the head intern", 11, 400, MUTED)
    s.text(500, 480, "Handoffs are lines in those files: deal signed → the head intern · proposal accepted → finance · questions from prospects → marketing", 12, 400, CREAM, "middle")
    s.text(500, 510, "Friday: every intern tidies its memory and promotes what worked into PLAYBOOK.md, with the evidence.", 12, 400, MINT, "middle")
    s.text(500, 540, "Files you own. Never in git. Synced only through a store you control.", 12, 700, GOLD, "middle")
    s.save("memory.svg")


def approval():
    s = Svg(1000, 330)
    s.title("Nothing goes out without you", "the sign-off flow for any email an intern drafts")
    steps = [("Intern drafts", ["in your voice;", "voice.py checks it"], GOLD),
             ("Draft card", ["the exact text, in your", "channel or a file"], GOLD),
             ("You sign off", ["a thumbs up or one", "command; 2 min to undo"], MINT),
             ("Verify + lock", ["the draft still", "matches the card"], GOLD),
             ("Head intern", ["sends that draft,", "once"], MINT)]
    for i, (t, sub, c) in enumerate(steps):
        x = 40 + i * 188
        s.card(x, 110, 160, 100, c)
        s.text(x + 14, 146, t, 16, 800)
        s.text(x + 14, 172, sub[0], 12, 400, MUTED)
        s.text(x + 14, 190, sub[1], 12, 400, MUTED)
        if i < len(steps) - 1:
            s.arrow(x + 168, 160, x + 184, 160)
    s.text(40, 258, "The guard lets a scheduled run send only a signed-off card, past its two minutes, once. Live, only the head", 12, 400, CREAM)
    s.text(40, 276, "intern can send, and only after your own message says send. A typed 'send' in the channel, or a sign-off on", 12, 400, CREAM)
    s.text(40, 294, "an older version of the card, doesn't count. Undo inside the two minutes and nothing happens.", 12, 400, CREAM)
    s.save("approval.svg")


def custom_vs_platform():
    s = Svg(1000, 730)
    s.title("Build your own, or use a ready-made bot?", "the trade, row by row")
    rows = [("Memory", "files you own", "the provider's systems"),
            ("What they know", "your files, pipeline, prices", "what you tell it"),
            ("The model", "any, chosen per job", "the provider's"),
            ("What's shared", "you decide, per tool", "the platform's settings"),
            ("Moving later", "copy a folder", "start again"),
            ("Time to start", "a coffee break, then a weekend", "minutes"),
            ("Cost", "your AI plan or API use", "a subscription"),
            ("Upkeep", "a little, by you", "none, by them")]
    s.card(330, 108, 300, 46, MINT, CREAM, 10); s.text(480, 138, "your own interns", 16, 800, INK, "middle")
    s.card(660, 108, 300, 46, MUTED, CREAM, 10); s.text(810, 138, "a ready-made bot", 16, 800, INK, "middle")
    for i, (label, mine, theirs) in enumerate(rows):
        y = 180 + i * 62
        s.text(40, y + 28, label, 15, 700, CREAM)
        s.pill(330, y, 300, 44, MINT); s.text(480, y + 28, mine, 13, 700, INK, "middle")
        s.pill(660, y, 300, 44, MUTED); s.text(810, y + 28, theirs, 13, 400, CREAM, "middle")
    s.text(40, 700, "A ready-made bot is quicker to start and someone else runs it. Yours takes shaping and gets better the longer you keep it.", 13, 400, GOLD)
    s.save("custom-vs-platform.svg")


def report():
    """A mock morning report, fake business and fake people, so readers can see what lands at 08:30."""
    s = Svg(760, 520)
    s.card(30, 30, 690, 450, MINT, CREAM, 16)
    s.dot(66, 70, 16, GOLD); s.text(66, 75, "T", 14, 800, INK, "middle")
    s.text(92, 66, "Head intern (Theo)", 15, 800); s.text(92, 84, "08:30 · the morning report (example)", 11, 400, MUTED)
    lines = [("Win the Harbour Studio call at 11: the ask is a start date.", 15, 800, INK),
             ("", 8, 400, INK),
             ("START HERE", 11, 800, MUTED),
             ("1. 09:00  Reply to Sam at Harbour Studio: draft ready to sign off", 13, 400, INK),
             ("2. 09:15  Ten calls from today's sheet, best window 10-11", 13, 400, INK),
             ("3. 11:00  Harbour Studio call: prep pack on the board", 13, 400, INK),
             ("", 8, 400, INK),
             ("SALES · Two replies overnight; one wants a proposal by Friday", 13, 400, INK),
             ("MARKETING · Post options ready; option B tests a question hook", 13, 400, INK),
             ("FINANCE · Cash is fine; one invoice is 9 days overdue, chaser drafted", 13, 400, INK),
             ("", 8, 400, INK),
             ("ONE DECISION: send the proposal at the standard price, or offer a pilot?", 13, 800, INK),
             ("", 8, 400, INK),
             ("Orders · Sales: proposal draft by Thursday · Finance: chase invoice 0042", 12, 400, MUTED)]
    y = 122
    for t, size, w, c in lines:
        if t:
            s.text(60, y, t, size, w, c)
        y += size + 13
    s.text(30, 508, "Example only: a made-up business. Yours is built from your interns' notes each morning.", 11, 400, CREAM)
    s.save("report.svg")


def card():
    """A mock draft card, as it arrives on your phone."""
    s = Svg(560, 400)
    s.card(30, 30, 490, 320, GOLD, CREAM, 16)
    s.text(56, 66, "Draft card · sales (Ella)", 14, 800); s.text(56, 84, "to sam@harbour.example · reply in thread", 11, 400, MUTED)
    body = ["Hi Sam,", "", "Thanks for the notes. Friday works for the proposal,",
            "and I'll include the pilot option you asked about.", "", "Speak soon,", "Alex"]
    y = 120
    for line in body:
        if line:
            s.text(56, y, line, 13)
        y += 20
    s.pill(56, 282, 150, 40, MINT); s.text(131, 307, "Approve", 14, 800, INK, "middle")
    s.pill(220, 282, 150, 40, MUTED); s.text(295, 307, "Edit in thread", 13, 700, CREAM, "middle")
    s.text(30, 378, "Example only. React to approve; it sends two minutes later unless you undo.", 11, 400, CREAM)
    s.save("card.svg")


INTERNS = [
    {"name": "Theo", "role": "head intern", "key": "orchestrator", "title": "head intern · orchestrator",
     "tag": "plans your day, runs the team",
     "tools": ["calendar · the board · inbox · team status", "the only one who sends, on your sign-off"],
     "lines": ["reads every intern · one plan", "orders the team · the only sender"],
     "reads": ["calendar", "the board", "your inbox", "team status"],
     "writes": ["morning report", "orders", "board cards (live)", "email drafts → sends on your word"],
     "never": ["others' meetings", "invites", "deletes"]},
    {"name": "Ella", "role": "sales", "key": "sales", "title": "sales", "tag": "preps your sales",
     "tools": ["CRM · inbox · call notes · pricing doc", "contacted.py · the outbound sheet"],
     "lines": ["the outbound sheet · CRM", "follow-ups · proposals"],
     "reads": ["CRM", "inbox", "call notes", "pricing doc"],
     "writes": ["outbound sheet", "CRM notes, stages", "email + message drafts", "proposals"],
     "never": ["sending", "inventing a price", "cold contact mid-thread"]},
    {"name": "Chris", "role": "marketing", "key": "marketing", "title": "marketing", "tag": "drafts the marketing",
     "tools": ["past posts · analytics · brand kit", "voice.py · hooks.py"],
     "lines": ["posts · calendar · images", "events · what gets measured"],
     "reads": ["your past posts", "analytics", "brand kit", "transcripts, with permission"],
     "writes": ["post drafts", "content calendar", "images", "event kits"],
     "never": ["posting as you", "naming private clients", "untrue hooks"]},
    {"name": "Arthur", "role": "finance", "key": "finance", "title": "finance", "tag": "minds the money",
     "tools": ["bank statements · invoices · ledger", "categorise.py · truelayer.py (read-only)"],
     "lines": ["ledger · forecast · invoices", "chasers · never moves a penny"],
     "reads": ["bank statements", "invoices", "ledger", "receipts"],
     "writes": ["ledger", "13-week forecast", "invoice drafts", "chase drafts"],
     "never": ["moving money", "keys in files", "figures in shared channels"]},
]

if __name__ == "__main__":
    team(INTERNS); team_row(INTERNS); day(); tools(INTERNS); memory(INTERNS); approval(); custom_vs_platform()
    report(); card()
    print("drew 9 diagrams in", HERE)
