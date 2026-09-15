# Claude Code instructions for this repo

## Never apply yourself — mandatory, no exceptions

Only the supervised bot (`NaukriKeepalive` scheduled task → `naukri_keepalive.ps1 -AllDay` →
`run_naukri_unattended.py --all-day`) may click Apply, click Save on a chat-drawer question, or
submit a job application — by any method, in any Edge session, ever, including "just to test."

You may read/edit code, restart the *supervised* bot process, and drive its Edge session **read-only**
for diagnosis (sample a page's DOM, read state) — but never click Apply/Save/submit yourself, never
call the apply-path functions directly (`_unattended_apply_one`, `_apply_to_single_job`,
`_save_aware_submit`, `naukri_bot.chatdrawer.engine.run()`), and never run a second ad-hoc bot instance.

To check whether something works: restart the supervised bot and watch it with the dedicated,
read-only watcher — `watch.cmd live` or `watch.cmd postmortem --since 6h` (see `naukri_watch/`). That
tool exists specifically so no agent ever needs to apply to a job itself to find out.

Full rule, with the MUST-NOT / MAY breakdown: see this repo's own `AGENTS.md`.

## Current goal (started 2026-09-15 19:20 IST, user-set)

**Goal: two consecutive hours of the auto-apply bot running with zero unexplained inactivity and zero
unhandled errors**, verified live by `watch.cmd` (never by applying to anything — see above), before
this monitoring loop is considered done.

- The watcher stays attached (`watch.cmd live`, read-only over CDP) continuously.
- **Inactivity >5 minutes** that isn't an already-known/logged pause (the daily apply-quota sleep,
  the between-cycle cooldown) is treated as a failure: diagnose it for real (read the log, the
  watcher's `incidents.jsonl`, check whether the bot's Edge session is actually still alive —
  a dead browser behind a live Python PID has already happened once tonight, silently, for ~50
  minutes, undetected until asked about directly), fix the root cause, restart the *supervised* bot,
  resume watching.
- Any watcher-reported error (`FALSE_CONFIRM`, `FALSE_DISCARD`, `APPLICATION_REJECTED`,
  `EXTERNAL_APPLY_CLICKED`, a Python traceback, etc.) also resets the clean-streak clock, whether or
  not it required a code fix.
- A fix that changes behavior gets a real restart and real observation before the streak clock
  restarts — never declared done on a code diff alone.
- The 2-hour clean streak can only start accruing once the bot is actually applying (i.e., after the
  daily quota resets at 2026-09-16 00:05 IST) — the quota-sleep itself is expected quiet time, not
  part of either the failure count or the 2 clean hours.
- Stop condition: a full 2-hour streak with zero interventions needed, **or** the user says stop.

If you are a fresh agent picking this up (any harness — Claude Code, OpenCode, Pi/picode): check
`git log --oneline -10` in this repo for what's already been tried tonight before repeating a fix.
