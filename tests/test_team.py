"""Tests for the team scripts and install.py. Run: python3 -m unittest discover tests"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "team", "bin")
sys.path.insert(0, BIN)
import common  # noqa: E402
import guard  # noqa: E402
import orders  # noqa: E402
import send_ok  # noqa: E402
import tick  # noqa: E402
import voice  # noqa: E402


class SelfTests(unittest.TestCase):
    """Every script's --test must pass; they are the executable spec."""

    def test_each_script(self):
        for name in ("boot", "guard", "send_ok", "orders", "brief", "tick", "approvals", "slack", "open", "voice"):
            r = subprocess.run([sys.executable, os.path.join(BIN, f"{name}.py"), "--test"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{name}: {r.stdout}{r.stderr}")

    def test_check_private(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "check_private.py"), "--test"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


class Guard(unittest.TestCase):
    def setUp(self):
        os.environ["SEND_OK_FILE"] = os.path.join(tempfile.mkdtemp(), "ok.json")
        send_ok.TOKEN = os.environ["SEND_OK_FILE"]

    def test_specialists_never_send(self):
        for a in ("ella", "chris", "arthur"):
            self.assertIsNotNone(guard.check(a, "mcp__gmail__send_message", {"to": ["x@y.com"]}))

    def test_orchestrator_needs_arming_then_one_send(self):
        orch = common.orchestrator()
        self.assertIsNotNone(guard.check(orch, "mcp__gmail__send_message", {}))
        self.assertTrue(send_ok.arm("yes, send it"))
        self.assertIsNone(guard.check(orch, "mcp__gmail__send_message", {}))
        self.assertIsNotNone(guard.check(orch, "mcp__gmail__send_message", {}))

    def test_nobody_deletes(self):
        self.assertIsNotNone(guard.check("theo", "mcp__board__delete_action", {}))
        self.assertIsNotNone(guard.check("theo", "Bash", {"command": "rm -rf /tmp/x"}))

    def test_scheduled_is_stricter(self):
        self.assertIsNone(guard.check("chris", "Bash", {"command": "git push"}, scheduled=False))
        self.assertIsNotNone(guard.check("chris", "Bash", {"command": "git push"}, scheduled=True))


class SignOff(unittest.TestCase):
    """Only the human signs off: no reaction tools, no inline approve, no editing a signed-off draft (round-5 review)."""

    def setUp(self):
        import approvals
        self.approvals = approvals
        approvals.STATE = os.path.join(tempfile.mkdtemp(), "a.json")
        approvals.common.INBOX = tempfile.mkdtemp()
        approvals._test_keys = None

    def test_send_names_normalised_on_any_server(self):
        for tool in ("mcp__outlook__sendMail", "mcp__x__sendEmail", "mcp__y__send-email", "mcp__z__Send_Email",
                     "mcp__mail__replyAll", "mcp__mail__forwardMessage"):
            self.assertTrue(guard.is_email_send(tool), tool)
            for a in ("ella", "chris", "arthur"):
                self.assertIsNotNone(guard.check(a, tool, {}), f"{a} {tool}")
        for tool in ("mcp__gmail__list_sent_messages", "mcp__mail__getSendStatus", "mcp__gmail__create_draft"):
            self.assertFalse(guard.is_email_send(tool), tool)

    def test_reactions_blocked_for_every_intern(self):
        for tool in ("mcp__claude_ai_Slack__slack_add_reaction", "mcp__teams__addReaction", "mcp__x__remove-reaction"):
            for a in ("theo", "ella", "chris", "arthur"):
                for scheduled in (False, True):
                    self.assertIsNotNone(guard.check(a, tool, {"name": "+1"}, scheduled), f"{a} {tool}")
        self.assertIsNone(guard.check("chris", "mcp__slack__slack_get_reactions", {}))
        for a in ("theo", "ella", "chris", "arthur"):
            with open(os.path.join(ROOT, "agents", a, ".claude", "settings.json")) as fh:
                deny = json.load(fh)["permissions"]["deny"]
            for d in ("mcp__*__slack_add_reaction", "mcp__*__addReaction", "mcp__*__add_reaction"):
                self.assertIn(d, deny, a)

    def test_inline_approve_fails(self):
        cmd = "import approvals; print(approvals.approve('c1'))"
        self.assertIsNotNone(guard.check(common.orchestrator(), "Bash", {"command": f'python3 -c "{cmd}"'}))
        base = {k: v for k, v in os.environ.items() if k not in self.approvals.AGENT_MARKERS}
        for env, why in ((dict(base, TEAM_AGENT="theo"), "under an agent"), (base, "no terminal")):
            r = subprocess.run([sys.executable, "-c", cmd], cwd=BIN, env=env, stdin=subprocess.DEVNULL,
                               capture_output=True, text=True)
            self.assertIn("refused", r.stdout, why)

    def test_lock_needs_verify_and_signed_off_drafts_are_frozen(self):
        import time
        ap = self.approvals
        ap._test_keys = ap.test_keys()
        cid = ap.card("ella", "d1", "a@b.com", "Hi", "Body")
        ap.approve(cid, answer=lambda code: code, at=time.time() - ap.DELAY_S - 1)
        self.assertFalse(ap.lock(cid))
        for tool in ("mcp__gmail__update_draft", "mcp__outlook__updateDraft", "mcp__x__edit-draft"):
            self.assertIsNotNone(guard.check("ella", tool, {"draftId": "d1"}), tool)
        self.assertIsNone(guard.check("ella", "mcp__gmail__update_draft", {"draftId": "d2"}))
        self.assertEqual(ap.verify(cid, "a@b.com", "", "Hi", "Body"), "ok")
        self.assertTrue(ap.lock(cid))
        self.assertTrue(ap.send_allowed("d1"))
        ap._test_keys = None

    def test_hand_written_record_never_sends(self):
        import time
        ap = self.approvals
        cid = ap.card("ella", "d1", "a@b.com", "Hi", "Body")
        ap._record(cid, True, at=time.time() - ap.DELAY_S - 1, via="terminal")
        ap.verify(cid, "a@b.com", "", "Hi", "Body")
        ap.lock(cid)
        self.assertFalse(ap.send_allowed("d1"))


class RoundSix(unittest.TestCase):
    """The round-6 review's break attempts: a faked terminal, disguised names, other id and send spellings."""

    def test_break_attempts_blocked(self):
        orch = common.orchestrator()
        for cmd in ("env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT script -q /dev/null python3 ../../team/bin/appro*.py approve --card C",
                    "python3 -c \"import importlib; importlib.import_module('appro'+'vals')\"",
                    "sec''urity find-generic-password -s agent-interns-signing-key -w",
                    "cat ~/.config/agent-interns/sign*",
                    "python3 -c 'import pty; pty.spawn([\"python3\"])'",
                    "CLAUDECODE= python3 x.py"):
            self.assertIsNotNone(guard.check(orch, "Bash", {"command": cmd}), cmd)
        for tool in ("mcp__mail__dispatch", "mcp__outlook__emails_create", "mcp__helpdesk__respond_to_email",
                     "mcp__mail__deliver_email"):
            self.assertIsNotNone(guard.check("chris", tool, {}), tool)

    def test_draft_ids_however_passed(self):
        for inp in ({"draftId": "d"}, {"draft_id": "d"}, {"draftID": "d"}, {"draft": {"id": "d"}}):
            self.assertEqual(guard.draft_ids(inp), ["d"], inp)
        for tool in ("mcp__mail__save_draft", "mcp__mail__saveDraft", "mcp__outlook__drafts_update"):
            self.assertTrue(guard.is_draft_edit(tool), tool)

    def test_only_the_orchestrator_posts_in_chat(self):
        for a in ("ella", "chris", "arthur"):
            self.assertIsNotNone(guard.check(a, "mcp__slack__slack_send_message", {"text": "hi"}), a)
        self.assertIsNotNone(guard.check(common.orchestrator(), "mcp__slack__slack_send_message", {"text": "hi"}, True))

    def test_no_code_on_file(self):
        import approvals
        approvals.STATE = os.path.join(tempfile.mkdtemp(), "a.json")
        approvals.common.INBOX = tempfile.mkdtemp()
        cid = approvals.card("ella", "d1", "a@b.com", "Hi", "Body")
        with open(os.path.join(approvals.common.INBOX, approvals.common.today(), "cards.md")) as fh:
            text = fh.read()
        self.assertNotIn("code", text)
        self.assertNotIn(approvals._load()[cid]["fp"][:4], text)


class SendPhrases(unittest.TestCase):
    def test_negations_and_questions_never_arm(self):
        for p in ("don't send it", "should I send it?", "I'll send it myself", "no sending remember"):
            self.assertFalse(send_ok.says_send(p), p)

    def test_plain_instruction_arms(self):
        for p in ("send it", "ok send", "go ahead and send the email"):
            self.assertTrue(send_ok.says_send(p), p)


class Orders(unittest.TestCase):
    def setUp(self):
        orders.common.INBOX = tempfile.mkdtemp()

    def _give(self, do, date="2026-01-05"):
        p = os.path.join(orders.common.INBOX, "o.json")
        with open(p, "w") as f:
            json.dump([{"to": "ella", "do": do, "why": "because"}], f)
        return orders.give(p, date, agents=["theo", "ella"])

    def test_forbidden_verbs_blocked(self):
        for do in ("Send the proposal", "Delete the old cards", "Pay the invoice", "Invite them to the call"):
            self.assertIn("blocked", self._give(do), do)

    def test_short_job_given_and_reported(self):
        self.assertEqual(self._give("Shortlist 20 warm contacts")["given"], 1)
        orders.common.now = lambda: datetime.datetime(2026, 1, 5, 9, 0)
        self.assertTrue(orders.report("ella", 1, "blocked", "no CRM access", "2026-01-05").startswith("reported"))
        today, recap, prev = orders.for_brief("2026-01-06")
        self.assertIn("1 blocked", recap)


class Schedule(unittest.TestCase):
    def test_shipped_schedule_is_valid(self):
        jobs = tick.load_schedule(os.path.join(ROOT, "team", "schedule.json"))
        self.assertGreaterEqual(len(jobs), 5)
        when = datetime.datetime(2026, 1, 5, 7, 0)
        for j in jobs:
            self.assertIsNotNone(tick.next_run(j, when), j["id"])
            self.assertTrue(os.path.isdir(os.path.join(ROOT, "agents", j["agent"])), j["agent"])


class Voice(unittest.TestCase):
    def test_banned_list_read_from_voice_md(self):
        phrases = voice.banned_phrases(os.path.join(ROOT, "team", "voice", "VOICE.md"))
        self.assertIn("Great question", phrases)
        self.assertFalse(voice.check("Great question! Let's go.", phrases)["ok"])


class Install(unittest.TestCase):
    def test_dry_run_lists_four_interns(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        for role in ("orchestrator", "sales", "marketing", "finance"):
            self.assertIn(role, r.stdout)
        self.assertIn("dry run", r.stdout)

    def test_help_never_installs(self):
        def snapshot():
            paths = [os.path.join(ROOT, "team", "team.json"), os.path.join(ROOT, "team", "schedule.json"),
                     os.path.join(ROOT, "bin"), os.path.join(ROOT, "agents", "theo", "AGENT.md")]
            return [(p, os.path.exists(p) and os.stat(p).st_mtime_ns) for p in paths]
        before = snapshot()
        for arg in ("--help", "-h"):
            r = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), arg, "--yes"], capture_output=True,
                               text=True, stdin=subprocess.DEVNULL)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Usage:", r.stdout)
        self.assertEqual(snapshot(), before)

    def test_answers_as_json_never_touch_a_shell(self):
        import io
        sys.path.insert(0, ROOT)
        import install
        words = {"owner": "Sam \"$(whoami)\"", "business": "Harbour; rm -rf ~", "names": ["Max", "", "Chris"]}
        argv = install.with_answers(["install.py", "--yes", "--answers", "-"], stdin=io.StringIO(json.dumps(words)))
        answers, names = install.gather(argv, ask_questions=False)
        self.assertEqual((answers["owner"], answers["business"]), (words["owner"], words["business"]))
        self.assertEqual(names["orchestrator"], "Max")
        with self.assertRaises(SystemExit):
            install.with_answers(["install.py", "--answers", "-"], stdin=io.StringIO('{"evil": 1}'))

    def test_fill_renames_everywhere(self):
        sys.path.insert(0, ROOT)
        import install
        text = "You are **Theo**. theo-brief runs. Ella helps."
        out = install.fill(text, {"owner": "Sam", "business": "B", "goal": "G", "timezone": "UTC"},
                           {"orchestrator": "Max", "sales": "Ella", "marketing": "Chris", "finance": "Arthur"}, install.DEFAULT_NAMES)
        self.assertEqual(out, "You are **Max**. max-brief runs. Ella helps.")

    def test_every_agent_has_the_files(self):
        for a in ("theo", "ella", "chris", "arthur"):
            for f in ("AGENT.md", "OPERATING.md", "PLAYBOOK.md", "CLAUDE.md", "AGENTS.md", "agent.json", "memory/MEMORY.md",
                      "memory/questions.md", "memory/log.md", ".claude/settings.json"):
                self.assertTrue(os.path.isfile(os.path.join(ROOT, "agents", a, f)), f"{a}/{f}")
            with open(os.path.join(ROOT, "agents", a, ".claude", "settings.json")) as fh:
                s = json.load(fh)
            self.assertIn("PreToolUse", s["hooks"])
            self.assertIn("mcp__.*", s["hooks"]["PreToolUse"][0]["matcher"])   # the guard sees every MCP tool
            deny = s["permissions"]["deny"]
            for d in ("mcp__*__delete_*", "mcp__*__trash_*", "mcp__*__make_payment"):
                self.assertIn(d, deny, f"{a} must deny {d}")
            if a != "theo":
                self.assertIn("mcp__*__send_message", deny)
            else:
                self.assertIn("UserPromptSubmit", s["hooks"])
                # a deny beats every hook, so denying his sends would block the card you signed off too
                self.assertFalse([d for d in deny if "send" in d or "reply" in d], deny)

    def test_skill_paths_resolve_from_the_agent_folder(self):
        """Skills, AGENT.md and OPERATING.md run inside agents/<name>/, so every team path must be ../../team/."""
        import re
        for a in ("theo", "ella", "chris", "arthur"):
            folder = os.path.join(ROOT, "agents", a)
            files = [os.path.join(folder, f) for f in ("AGENT.md", "OPERATING.md", "AGENTS.md")]
            for d, _, names in os.walk(os.path.join(folder, ".claude", "skills")):
                files += [os.path.join(d, n) for n in names if n.endswith(".md")]
            for path in files:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                bare = re.findall(r"(?<![./\w])team/(?:bin|inbox|status|voice|TEAM|schedule)", text)
                self.assertEqual(bare, [], f"{path}: use ../../team/")
                for ref in re.findall(r"\.\./\.\./team/(?:bin/\w+\.py|TEAM\.md|schedule\.json|voice/\w+\.md)", text):
                    self.assertTrue(os.path.exists(os.path.normpath(os.path.join(folder, ref))), f"{path}: {ref}")
        with open(os.path.join(ROOT, "team", "schedule.json")) as fh:
            for job in json.load(fh)["jobs"]:
                self.assertNotRegex(job["prompt"], r"\(team/", job["id"])

    def test_every_scheduled_skill_exists(self):
        with open(os.path.join(ROOT, "team", "schedule.json")) as fh:
            jobs = json.load(fh)["jobs"]
        for job in jobs:
            if job["prompt"].startswith("/"):
                skill = job["prompt"][1:].split()[0]
                path = os.path.join(ROOT, "agents", job["agent"], ".claude", "skills", skill, "SKILL.md")
                self.assertTrue(os.path.isfile(path), f"{job['id']}: no skill {skill}")
        # what the README says they do on their own
        runs = {(j["agent"], j["prompt"].split()[0]) for j in jobs}
        for pair in (("ella", "/today"), ("chris", "/post"), ("chris", "/score"), ("arthur", "/books"),
                     ("arthur", "/pulse"), ("theo", "/brief"), ("theo", "/health")):
            self.assertIn(pair, runs)

    def test_agents_md_matches_install(self):
        sys.path.insert(0, ROOT)
        import install
        for folder, role in (("theo", "orchestrator"), ("ella", "sales"), ("chris", "marketing"), ("arthur", "finance")):
            with open(os.path.join(ROOT, "agents", folder, "AGENTS.md"), encoding="utf-8") as fh:
                self.assertEqual(fh.read(), install.agents_md(folder, role, install.DEFAULT_NAMES[role]), folder)

    def test_install_rerun_swaps_old_answers(self):
        sys.path.insert(0, ROOT)
        import install
        first = install.fill("Goal: {{GOAL}}. For {{OWNER}} at {{BUSINESS}}. Samantha stays.",
                             {"owner": "Sam", "business": "Harbour", "goal": "ten clients", "timezone": "UTC"},
                             install.DEFAULT_NAMES, install.DEFAULT_NAMES)
        self.assertEqual(first, "Goal: ten clients. For Sam at Harbour. Samantha stays.")
        again = install.fill(first, {"owner": "Jo", "business": "Harbour", "goal": "launch the course", "timezone": "UTC"},
                             install.DEFAULT_NAMES, install.DEFAULT_NAMES,
                             {"owner": "Sam", "business": "Harbour", "goal": "ten clients", "timezone": "UTC"})
        self.assertEqual(again, "Goal: launch the course. For Jo at Harbour. Samantha stays.")   # whole words only
        blank = install.fill("Goal: {{GOAL}}.", {"owner": "Jo", "goal": ""}, install.DEFAULT_NAMES, install.DEFAULT_NAMES)
        self.assertEqual(blank, "Goal: {{GOAL}}.")                                               # blank keeps the placeholder

    def test_install_flags_need_no_questions(self):
        sys.path.insert(0, ROOT)
        import install
        answers, names = install.gather(["install.py", "--yes", "--owner", "Sam", "--goal", "ten clients",
                                         "--names", "Max,,Chris", "--tool", "codex"], ask_questions=False)
        self.assertEqual((answers["owner"], answers["goal"], answers["tool"], answers["runner"]),
                         ("Sam", "ten clients", "codex", "codex exec"))
        self.assertEqual(names, {"orchestrator": "Max", "sales": "Ella", "marketing": "Chris", "finance": "Arthur"})
        self.assertIn("onboard", install.agents_md("theo", "orchestrator", "Theo"))
        self.assertNotIn("onboard", install.agents_md("ella", "sales", "Ella"))

    def test_timezone_detection(self):
        sys.path.insert(0, ROOT)
        import install
        old = os.environ.get("TZ")
        try:
            os.environ["TZ"] = "America/Chicago"
            self.assertEqual(install.detect_timezone(), "America/Chicago")
            os.environ.pop("TZ")
            self.assertRegex(install.detect_timezone(), r"^[A-Za-z_]+(/[A-Za-z_+-]+)*$")
        finally:
            if old is not None:
                os.environ["TZ"] = old

    def test_gitignore_keeps_private_files_out(self):
        sys.path.insert(0, ROOT)
        import install
        self.assertEqual(install.ensure_gitignore(os.path.join(ROOT, ".gitignore")), [])
        path = os.path.join(tempfile.mkdtemp(), ".gitignore")
        with open(path, "w") as fh:
            fh.write("agents/*/out/\n")
        missing = install.ensure_gitignore(path)
        self.assertNotIn("agents/*/out/", missing)
        self.assertIn("agents/*/memory/*.md", missing)
        self.assertEqual(install.ensure_gitignore(path), [])


if __name__ == "__main__":
    unittest.main()
