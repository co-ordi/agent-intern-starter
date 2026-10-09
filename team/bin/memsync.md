# Memory sync: when your interns run in more than one place

Everything an intern remembers lives in files (`agents/<name>/memory/`). On one machine that is all you need: the
files are the memory, and git ignores them. The moment the same intern runs somewhere else too (a cloud routine, a
second laptop), the two copies drift. This note is the pattern that stops that. It is on the roadmap as a script;
until then, pick one of the three.

## The rules a sync has to keep

- **Memory is private.** It never goes in git. It travels encrypted or inside something you already trust.
- **Last writer wins per file**, decided with a checksum of the version each side last saw, so an unchanged copy
  never overwrites a newer one.
- **Append-only logs merge line by line** (`memory/log.md`), so two runs on the same day both keep their lines.
- **Sync never deletes.** A file missing on one side comes back from the other.
- **Sync at the edges:** pull on SessionStart, push on Stop, so a session always opens with the latest memory.

## Three ways to do it

1. **One machine (default).** Nothing to do. Your interns run on your computer, cron runs them while it is on.
2. **A private store you already have.** A small table in the database behind your dashboard, or a private
   object bucket: one row per `(agent, path)` with the content and its checksum. Two hooks (`pull` on
   SessionStart, `push` on Stop) move changed files. About 150 lines of Python; the orchestrator can write it.
3. **A private git repo for memory only.** Separate from this one, never public, pulled and pushed by the same
   two hooks. Simplest if you are comfortable with git; the log merge needs a `union` merge driver.

Whichever you choose, add the pull and push commands to each agent's `.claude/settings.json` hooks next to
`boot.py`, and keep the Finance intern's data out of it unless the store is encrypted at rest.
