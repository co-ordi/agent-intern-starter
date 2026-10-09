"""Tests for the interns' own tools (sales' contacted check, marketing's hook score, finance's categoriser and bank client).
Run: python3 -m unittest discover tests"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTHUR = os.path.join(ROOT, "agents", "arthur", "tools")
ELLA = os.path.join(ROOT, "agents", "ella", "tools")
CHRIS = os.path.join(ROOT, "agents", "chris", "tools")
sys.path.insert(0, ARTHUR)
import categorise  # noqa: E402
import truelayer  # noqa: E402


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True)


class SelfTests(unittest.TestCase):
    def test_each_tool(self):
        for path in (os.path.join(ELLA, "contacted.py"), os.path.join(CHRIS, "hooks.py"), os.path.join(ARTHUR, "categorise.py"),
                     os.path.join(ARTHUR, "truelayer.py")):
            r = run(path, "--test")
            self.assertEqual(r.returncode, 0, f"{path}: {r.stdout}{r.stderr}")


class Categorise(unittest.TestCase):
    def test_sample_statement_renders(self):
        r = run(os.path.join(ARTHUR, "categorise.py"), os.path.join(ARTHUR, "sample.csv"), "--print")
        self.assertEqual(r.returncode, 0, r.stderr)
        for heading in ("## Month by month", "## Where the money went", "Tax year 2026/27", "Tax year 2025/26"):
            self.assertIn(heading, r.stdout)
        self.assertIn("TAILSPIN", r.stdout)            # the one merchant no rule matches is listed to check
        self.assertNotIn("£-", r.stdout)               # negatives read -£1.00, never £-1.00

    def test_tax_year_boundary(self):
        import datetime
        self.assertEqual(categorise.tax_year(datetime.date(2026, 4, 5)), "2025/26")
        self.assertEqual(categorise.tax_year(datetime.date(2026, 4, 6)), "2026/27")


class BankClientIsReadOnly(unittest.TestCase):
    def test_refuses_anything_but_token_and_data_reads(self):
        auth, api = truelayer.HOSTS["sandbox"]
        for method, url in (("POST", f"{api}/single-immediate-payments"), ("GET", f"{api}/payments/v3/x"),
                            ("POST", f"{api}/data/v1/accounts"), ("GET", "https://example.com/data/v1/me"),
                            ("POST", f"{auth}/api/delete")):
            with self.assertRaises(truelayer.ReadOnly, msg=f"{method} {url}"):
                truelayer.request("sandbox", method, url)

    def test_scopes_cannot_pay(self):
        self.assertNotIn("payment", truelayer.SCOPES)
        self.assertEqual(set(truelayer.SCOPES.split()), {"info", "accounts", "balance", "transactions", "offline_access"})


class NothingPrivateInOut(unittest.TestCase):
    def test_out_folders_are_ignored(self):
        for path in ("agents/arthur/out/money.md", "agents/ella/out/contacted.csv", "agents/arthur/memory/notes.md"):
            r = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True)
            if r.returncode == 128:
                self.skipTest("not a git checkout")
            self.assertEqual(r.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
