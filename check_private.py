#!/usr/bin/env python3
"""The privacy gate. Fails if anything private is about to be committed.

It reads a denylist you keep OUTSIDE the repo (one term per line; `PRIVATE_TERMS_FILE`, default
~/.agent-team-private-terms) and scans every tracked and staged text file for those terms, plus the usual secret
shapes (API keys, tokens, private keys). The list itself never enters the repo; `private-terms.example` shows
the idea. Wire it as a pre-commit hook (`ln -s ../../check_private.py .git/hooks/pre-commit`) or run it by hand
before a push.

Why: your interns know your clients, prices and inbox. A template built from a real team is one careless commit
away from publishing them. This makes that commit fail.

Setting up the denylist takes a minute: copy private-terms.example to ~/.agent-team-private-terms and replace the
examples with your own client names, people, email domains, channel names and prices. Without it, the scan still
checks for secrets.

Usage:  check_private.py           scan tracked + staged files; exit 1 on a hit
        check_private.py --all     scan every file in the folder, tracked or not
        check_private.py --test"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TERMS_FILE = os.environ.get("PRIVATE_TERMS_FILE") or os.path.expanduser("~/.agent-team-private-terms")
SECRET_SHAPES = [
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"), "Anthropic API key"),
    (re.compile(r"xox[bpsa]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"), "GitHub token"),
    (re.compile(r"AIza[0-9A-Za-z_-]{30,}"), "Google API key"),
    (re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"), "hard-coded credential"),
]
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".pdf", ".ico", ".woff", ".woff2", ".zip"}
SELF = os.path.basename(__file__)


def load_terms(path=TERMS_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            lines = [l.strip() for l in f]
    except OSError:
        return []
    return [l for l in lines if l and not l.startswith("#")]


def term_pattern(term):
    # short terms match whole words only, so "ark" doesn't fire on "market"
    esc = re.escape(term)
    return re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])" if len(term) <= 5 else esc, re.I)


def files_to_scan(everything=False):
    if everything or not os.path.isdir(os.path.join(ROOT, ".git")):
        out = []
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            out += [os.path.relpath(os.path.join(root, f), ROOT) for f in files]
        return out
    r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                       capture_output=True, text=True)
    return [l for l in r.stdout.splitlines() if l]


def scan(paths, terms):
    hits = []
    pats = [(term_pattern(t), t) for t in terms]
    for rel in paths:
        if os.path.splitext(rel)[1].lower() in SKIP_EXT or os.path.basename(rel) == SELF:
            continue
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            for pat, label in SECRET_SHAPES:
                if pat.search(line):
                    hits.append((rel, i, f"looks like a {label}"))
            for pat, t in pats:
                if pat.search(line):
                    hits.append((rel, i, f"private term: {t}"))
    return hits


def test():
    import tempfile
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "a.md"), "w") as f:
        f.write("Hello Acme, meet Zed.\ntoken = 'abcdefghijklmnop'\nThe market is open.\n")
    global ROOT
    ROOT = d
    hits = scan(["a.md"], ["Acme", "ark"])
    kinds = {h[2] for h in hits}
    ok = "private term: Acme" in kinds and "looks like a hard-coded credential" in kinds and len(hits) == 2
    print("check_private: ok" if ok else f"check_private: FAIL {hits}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__)
        sys.exit(0)
    if "--test" in sys.argv:
        test()
    terms = load_terms()
    if not terms:
        print(f"No denylist at {TERMS_FILE}. Create one (see private-terms.example); scanning for secrets only.")
    hits = scan(files_to_scan("--all" in sys.argv), terms)
    for rel, i, why in hits:
        print(f"{rel}:{i}: {why}")
    print(f"{len(hits)} hit(s) across the files scanned" if hits else "clean: no private terms, no secret shapes")
    sys.exit(1 if hits else 0)
