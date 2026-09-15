# Agent instructions for this repo

## Never apply yourself — mandatory, no exceptions

This repo runs a **supervised, unattended job-application bot**: the scheduled task `NaukriKeepalive`
→ `naukri_keepalive.ps1 -AllDay` → `run_naukri_unattended.py --all-day`, restarted automatically on
death. **That supervised process, and only that process, is allowed to click Apply, click Save on a
chat-drawer question, or otherwise submit a job application.** This applies to every agent CLI working
in this repo — Claude Code, OpenCode, Pi (picode), or anything else — with no exceptions for
"just testing," "just checking if the fix works," or "just this one job."

### You MUST NOT
1. **Never click Apply**, on a job card or a job page, in any Edge session (the bot's own profile at
   `browser_profile/edge_default`, or any other), by any method — a Selenium `.click()`, a CDP
   `Runtime.evaluate` synthetic click, `element.click()` via JS, keyboard Enter on a focused Apply
   button, anything that has the same effect.
2. **Never click Save on a chat-drawer question**, or fill a chat-drawer field with intent to submit
   it. Reading a drawer's current state (what `naukri_bot/chatdrawer/probe.js` does) is fine; acting
   on it — filling, clicking an option, pressing Save — is not, unless you *are* the supervised bot
   process itself.
3. **Never call the apply-path code yourself** as a way to "run" or "test" it: `_unattended_apply_one`,
   `_apply_to_single_job`, `_save_aware_submit`, `naukri_bot.chatdrawer.engine.run()`, or any
   equivalent in a later version of this code. These are the bot's own internals — read them, edit
   them, but do not invoke them against the live site from an agent session.
4. **Never start a second, ad-hoc instance of the bot** "just to watch it apply" or "to test the fix
   live." If you need to see current behavior, restart the *one* supervised instance (find its PID,
   kill it, let `naukri_keepalive.ps1` relaunch it — it does this within about a minute) rather than
   running a parallel copy.
5. **Never bypass or disable** the daily-quota pause (`_apply_blocked_until` in
   `run_naukri_unattended.py`) or any other safety gate to force more applications through.

### You MAY (this is normal, expected work)
- Read and edit the bot's code, `naukri_keepalive.ps1`, config, and any file in this repo.
- Restart the **supervised** bot process (kill its PID(s), let the keepalive supervisor relaunch it)
  to pick up a code change — this is how every fix in this repo has been verified.
- Drive the bot's own Edge session **read-only** for diagnosis: navigate to a page to sample its DOM,
  read text/attributes, run non-mutating JS via CDP or Selenium. This is not "applying" as long as
  nothing gets clicked that submits, saves, or advances an application (this is exactly how
  `naukri_bot/chatdrawer/probe.js` and the profile-page sampling in `naukri_bot/chatdrawer/profile_facts.py`
  were built and verified — read, don't act).
- Read the bot's own database (`naukri_jobs.db`), logs (`naukri_bot.log`, `naukri_keepalive.log`), and
  telemetry — all read-only.

### How to actually verify something works
Use the dedicated watcher — **that is what it is for**:
```
watch.cmd                        # live, read-only, attaches over CDP, until Ctrl+C
watch.cmd live --minutes 30
watch.cmd postmortem --since 6h  # from naukri_bot.log alone, no browser needed
```
It attaches to the bot's own Edge read-only (`naukri_watch/`), never clicks anything, and reports what
actually happened — outcomes, incidents, timing, every chat-window question and its answer — by
watching the *supervised bot* do the real work. If you're unsure whether a fix works, restart the bot
and read the watcher's report; never click through an application yourself to find out.

See `docs/STRUCTURAL_FAULTS.md` for why earlier fix attempts on this bot failed repeatedly, and
`README.md`'s "When in doubt: watch.cmd" section for the short version of the above.
