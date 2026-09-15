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
