#!/usr/bin/env python3
"""Arthur's bank connection: a small, read-only client for the TrueLayer Data API (v1, UK and EU open banking).

Written against TrueLayer's Data API docs (docs.truelayer.com, checked October 2026) and tested with mocked
responses. Try the sandbox first: it is the default, and TrueLayer's Mock Bank logs in with user `john`, password `doe`.

    # from console.truelayer.com (your app's settings); keep them in your shell profile or keychain, never in a file here
    export TRUELAYER_CLIENT_ID=...  TRUELAYER_CLIENT_SECRET=...

    python3 truelayer.py link                           # prints the auth link: open it, connect, copy the code shown
    python3 truelayer.py connect <code>                 # swaps the code for tokens, stored outside the repo
    python3 truelayer.py accounts                       # the accounts you chose to share
    python3 truelayer.py pull --from 2026-04-06         # transactions to a CSV that categorise.py reads
    python3 truelayer.py status                         # what the connection is and when consent runs out
    python3 truelayer.py disconnect                     # deletes the stored tokens from this machine
    add --live to any command for real banks once the sandbox works.

Read-only by design:
- The scopes are info, accounts, balance, transactions and offline_access. Nothing that can pay.
- The client only ever POSTs to the token endpoint and GETs paths under /data/v1. Any other URL is refused in code,
  so it cannot reach a payments endpoint even by mistake.
- Tokens live in ~/.config/agent-interns/truelayer-<env>.json with 600 permissions, or in the macOS keychain if you
  set TRUELAYER_KEYCHAIN=1. Never in the repo, never in Arthur's memory.

How long it lasts: an access token lasts an hour and refreshes itself. The refresh token keeps working for up to
90 days in the UK (it must be used within its first 30); after that the consent lapses and you run `link` again.

TrueLayer recommends its newer Data API v3 for brand-new integrations. This client speaks v1, which is fully
documented and has the Mock Bank; the HTTP layer is one function (`request`) if you move. In the US, Plaid plays
the same role. Python 3.9+, standard library only.

    truelayer.py --test     self-test (mocked HTTP, no network)"""
import argparse
import csv
import datetime
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HOSTS = {"sandbox": ("https://auth.truelayer-sandbox.com", "https://api.truelayer-sandbox.com"),
         "live": ("https://auth.truelayer.com", "https://api.truelayer.com")}
PROVIDERS = {"sandbox": "uk-cs-mock", "live": "uk-ob-all"}
SCOPES = "info accounts balance transactions offline_access"
DEFAULT_REDIRECT = "https://console.truelayer.com/redirect-page"
TOKEN_DIR = os.path.expanduser(os.environ.get("TRUELAYER_TOKEN_DIR", "~/.config/agent-interns"))
CSV_FIELDS = ["date", "description", "amount", "currency", "account", "transaction_id", "merchant", "category_hint"]

opener = urllib.request.urlopen  # swapped for a fake in the self-test


class ReadOnly(Exception):
    """Raised for any request outside the token endpoint and /data/v1 reads."""


def hosts(env):
    return HOSTS[env]


def creds():
    cid, secret = os.environ.get("TRUELAYER_CLIENT_ID"), os.environ.get("TRUELAYER_CLIENT_SECRET")
    if not cid or not secret:
        sys.exit("Set TRUELAYER_CLIENT_ID and TRUELAYER_CLIENT_SECRET (from console.truelayer.com) in your shell first.")
    return cid, secret


def request(env, method, url, data=None, token=None):
    """The one place this client talks to the network. Refuses anything that isn't a token call or a data read."""
    auth, api = hosts(env)
    if method == "POST" and url == f"{auth}/connect/token":
        pass
    elif method == "GET" and url.startswith(f"{api}/data/v1/"):
        pass
    else:
        raise ReadOnly(f"refused {method} {url}: this client only reads data")
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with opener(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"TrueLayer said {e.code}: {detail}") from None


# ---- token storage: outside the repo, 600, or the macOS keychain ------------------------------------------------

def _token_file(env):
    return os.path.join(TOKEN_DIR, f"truelayer-{env}.json")


def _use_keychain():
    return os.environ.get("TRUELAYER_KEYCHAIN") == "1" and platform.system() == "Darwin"


def save_tokens(env, tok):
    tok = dict(tok)
    tok["expires_at"] = time.time() + int(tok.get("expires_in") or 3600) - 60
    blob = json.dumps(tok)
    if _use_keychain():
        subprocess.run(["security", "add-generic-password", "-U", "-s", f"agent-interns-truelayer-{env}",
                        "-a", "tokens", "-w", blob], check=True, capture_output=True)
        return
    os.makedirs(TOKEN_DIR, mode=0o700, exist_ok=True)
    path = _token_file(env)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(blob)
    os.chmod(path, 0o600)


def load_tokens(env):
    try:
        if _use_keychain():
            r = subprocess.run(["security", "find-generic-password", "-s", f"agent-interns-truelayer-{env}",
                                "-a", "tokens", "-w"], capture_output=True, text=True, check=True)
            return json.loads(r.stdout)
        with open(_token_file(env)) as f:
            return json.load(f)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def forget_tokens(env):
    """Delete the stored tokens. True if there were any."""
    if _use_keychain():
        r = subprocess.run(["security", "delete-generic-password", "-s", f"agent-interns-truelayer-{env}", "-a", "tokens"],
                           capture_output=True)
        return r.returncode == 0
    try:
        os.remove(_token_file(env))
        return True
    except FileNotFoundError:
        return False


# ---- the flow -----------------------------------------------------------------------------------------------------

def auth_link(env, client_id, redirect=DEFAULT_REDIRECT, state="arthur"):
    auth, _ = hosts(env)
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect, "scope": SCOPES,
         "state": state, "providers": PROVIDERS[env]}
    return f"{auth}/?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def connect(env, code, redirect=DEFAULT_REDIRECT):
    cid, secret = creds()
    auth, _ = hosts(env)
    tok = request(env, "POST", f"{auth}/connect/token", {"grant_type": "authorization_code", "client_id": cid,
                  "client_secret": secret, "redirect_uri": redirect, "code": code})
    save_tokens(env, tok)
    return tok


def access_token(env):
    tok = load_tokens(env)
    if not tok:
        sys.exit("Not connected yet. Run `truelayer.py link`, then `truelayer.py connect <code>`.")
    if time.time() < tok.get("expires_at", 0):
        return tok["access_token"]
    if not tok.get("refresh_token"):
        sys.exit("The access token expired and there's no refresh token (offline_access). Run `link` again.")
    cid, secret = creds()
    auth, _ = hosts(env)
    try:
        new = request(env, "POST", f"{auth}/connect/token", {"grant_type": "refresh_token", "client_id": cid,
                      "client_secret": secret, "refresh_token": tok["refresh_token"]})
    except RuntimeError as e:
        sys.exit(f"Couldn't refresh ({e}). The consent has probably lapsed: run `link` and `connect` again.")
    new.setdefault("refresh_token", tok["refresh_token"])
    save_tokens(env, new)
    return new["access_token"]


def get(env, path, **params):
    _, api = hosts(env)
    url = f"{api}/data/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return request(env, "GET", url, token=access_token(env)).get("results", [])


def accounts(env):
    return get(env, "accounts")


def transactions(env, account_id, start, end):
    return get(env, f"accounts/{account_id}/transactions", **{"from": f"{start}T00:00:00", "to": f"{end}T23:59:59"})


def to_rows(txs, account_name):
    rows = []
    for t in txs:
        rows.append({"date": (t.get("timestamp") or "")[:10], "description": t.get("description", ""),
                     "amount": t.get("amount", 0), "currency": t.get("currency", ""), "account": account_name,
                     "transaction_id": t.get("transaction_id", ""), "merchant": t.get("merchant_name", ""),
                     "category_hint": " / ".join(t.get("transaction_classification") or [])})
    return rows


def write_csv(path, rows):
    """Append to the CSV, skipping transactions already in it (by transaction_id), so re-runs never duplicate."""
    seen, existing = set(), []
    if os.path.exists(path):
        with open(path, newline="") as f:
            existing = list(csv.DictReader(f))
        seen = {r.get("transaction_id") for r in existing}
    new = [r for r in rows if r["transaction_id"] not in seen]
    all_rows = sorted(existing + new, key=lambda r: r["date"])
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})
    return len(new)


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only TrueLayer client for Arthur.")
    p.add_argument("cmd", nargs="?", choices=["link", "connect", "accounts", "pull", "status", "disconnect"])
    p.add_argument("code", nargs="?")
    p.add_argument("--live", action="store_true", help="real banks (default: sandbox)")
    p.add_argument("--redirect", default=os.environ.get("TRUELAYER_REDIRECT_URI", DEFAULT_REDIRECT))
    p.add_argument("--from", dest="start", help="YYYY-MM-DD (default: 30 days ago)")
    p.add_argument("--to", dest="end", help="YYYY-MM-DD (default: today)")
    p.add_argument("--account", help="one account id (default: all)")
    p.add_argument("--out", help="CSV to append to (default: <arthur>/out/statement.csv)")
    p.add_argument("--test", action="store_true")
    a = p.parse_args(argv)
    if a.test:
        return selftest()
    if not a.cmd:
        p.error("choose a command: link, connect, accounts, pull, status or disconnect")
    env = "live" if a.live else "sandbox"
    if a.cmd == "link":
        cid, _ = creds()
        print(auth_link(env, cid, a.redirect))
        if env == "sandbox":
            print("\nSandbox: choose Mock Bank and log in as john / doe. Copy the code from the page you land on.")
    elif a.cmd == "connect":
        if not a.code:
            p.error("connect needs the code from the redirect page")
        connect(env, a.code, a.redirect)
        print("Connected. Tokens stored outside the repo. Try: truelayer.py accounts")
    elif a.cmd == "accounts":
        for acc in accounts(env):
            print(f"{acc.get('account_id')}  {acc.get('display_name', '')}  {acc.get('account_type', '')}  {acc.get('currency', '')}")
    elif a.cmd == "pull":
        end = a.end or str(datetime.date.today())
        start = a.start or str(datetime.date.today() - datetime.timedelta(days=30))
        out = a.out or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "statement.csv")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        added = 0
        for acc in accounts(env):
            if a.account and acc.get("account_id") != a.account:
                continue
            txs = transactions(env, acc["account_id"], start, end)
            added += write_csv(out, to_rows(txs, acc.get("display_name", acc["account_id"])))
        print(f"{added} new transactions → {out}\nNext: python3 categorise.py {out}")
    elif a.cmd == "status":
        me = get(env, "me")
        print(json.dumps(me[0] if me else {}, indent=2))
    elif a.cmd == "disconnect":
        print("Tokens deleted from this machine." if forget_tokens(env) else "No stored tokens to delete.")
        print("To withdraw the consent at the bank as well, remove TrueLayer in your bank's open banking or connected apps "
              "settings. Otherwise it lapses on its own when the consent period ends.")
    return 0


def selftest():
    import io
    import tempfile
    global opener, TOKEN_DIR
    TOKEN_DIR = tempfile.mkdtemp()
    os.environ.update({"TRUELAYER_CLIENT_ID": "test-id", "TRUELAYER_CLIENT_SECRET": "test-secret"})
    os.environ.pop("TRUELAYER_KEYCHAIN", None)
    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout=30):
        calls.append((req.get_method(), req.full_url, (req.data or b"").decode()))
        if req.full_url.endswith("/connect/token"):
            return Resp(json.dumps({"access_token": "AT", "expires_in": 3600, "refresh_token": "RT"}).encode())
        if req.full_url.endswith("/data/v1/accounts"):
            return Resp(json.dumps({"results": [{"account_id": "acc1", "display_name": "Business current"}]}).encode())
        if "/transactions?" in req.full_url:
            return Resp(json.dumps({"results": [
                {"transaction_id": "t1", "timestamp": "2026-04-07T00:00:00", "description": "ACME COFFEE CO",
                 "amount": -3.4, "currency": "GBP", "merchant_name": "Acme Coffee", "transaction_classification": ["Food", "Coffee"]},
                {"transaction_id": "t2", "timestamp": "2026-04-05T00:00:00", "description": "NORTHWIND LTD INVOICE 1048",
                 "amount": 1000.0, "currency": "GBP"}]}).encode())
        raise AssertionError(req.full_url)

    opener = fake
    ok = True
    link = auth_link("sandbox", "test-id")
    ok &= link.startswith("https://auth.truelayer-sandbox.com/?response_type=code") and "scope=info%20accounts%20balance%20transactions%20offline_access" in link
    ok &= "providers=uk-cs-mock" in link and "payments" not in link
    connect("sandbox", "CODE123")
    ok &= "grant_type=authorization_code" in calls[-1][2] and "code=CODE123" in calls[-1][2]
    ok &= oct(os.stat(_token_file("sandbox")).st_mode & 0o777) == "0o600"
    out = os.path.join(TOKEN_DIR, "statement.csv")
    rows = to_rows(transactions("sandbox", accounts("sandbox")[0]["account_id"], "2026-04-01", "2026-04-30"), "Business current")
    ok &= "from=2026-04-01T00%3A00%3A00" in calls[-1][1]
    ok &= write_csv(out, rows) == 2 and write_csv(out, rows) == 0          # re-runs never duplicate
    with open(out) as f:
        text = f.read()
    ok &= text.splitlines()[0] == ",".join(CSV_FIELDS) and "Food / Coffee" in text
    tok = load_tokens("sandbox")
    tok["expires_at"] = 0
    save_tokens("sandbox", {**tok, "expires_in": -100})
    access_token("sandbox")
    ok &= "grant_type=refresh_token" in calls[-1][2]
    for bad in (("POST", "https://api.truelayer-sandbox.com/v3/payments"), ("GET", "https://api.truelayer-sandbox.com/v3/payments/x"),
                ("POST", "https://api.truelayer-sandbox.com/data/v1/accounts"), ("GET", "https://example.com/data/v1/accounts")):
        try:
            request("sandbox", bad[0], bad[1])
            ok = False
        except ReadOnly:
            pass
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import categorise
    parsed = categorise.read_rows(text)
    ok &= len(parsed) == 2 and parsed[0]["amount"] == 1000.0
    ok &= forget_tokens("sandbox") and load_tokens("sandbox") is None and not forget_tokens("sandbox")
    print("truelayer: ok" if ok else f"truelayer: FAIL {calls}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
